# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The real database code for configuration versions (table bot_config_versions).
# Concurrency: 🔒 A database rule allows only ONE published version per bot; two simultaneous
#              publishes -> the loser gets 409.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQLAlchemy implementation of BotConfigRepository. Session must be tenant-bound (RLS)."""

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From sqlalchemy — SQLAlchemy, our database toolkit: func = SQL functions such as now() or
#   max(); select = builds a SELECT query; update = builds an UPDATE query.
from sqlalchemy import func, select, update

# From sqlalchemy.exc — database errors: IntegrityError = a database rule was broken (e.g.
#   duplicate).
from sqlalchemy.exc import IntegrityError

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncSession =
#   one unit of database work.
from sqlalchemy.ext.asyncio import AsyncSession

# From saathi.modules.tenancy.adapters.config_mapper — BotConfig <-> JSON conversion:
#   config_from_json = JSON -> BotConfig; config_to_json = BotConfig -> JSON.
from saathi.modules.tenancy.adapters.config_mapper import config_from_json, config_to_json

# From saathi.modules.tenancy.adapters.orm — the tenancy table classes: BotConfigVersionRow =
#   bot_config_versions table.
from saathi.modules.tenancy.adapters.orm import BotConfigVersionRow

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfigVersion = one saved version; ConfigStatus = draft/published/archived.
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion, ConfigStatus

# From saathi.platform.db.errors — reads which database rule was broken: violated_constraint =
#   name of the broken rule.
from saathi.platform.db.errors import violated_constraint

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data.
from saathi.platform.errors import ConflictError

# Database rule name -> friendly message:
_CONFLICTS = {
    # two saves got the same version number at the same moment;
    "uq_bot_config_versions_bot_version": "the configuration was saved concurrently; try again",
    # two publishes at the same moment (only one may win).
    "uq_bot_config_versions_one_published": "another publish is in progress; try again",
}


# Duplicate version number or double publish -> 409 conflict.
def _conflict_or_raise(exc: IntegrityError) -> None:
    # Find a friendly message for the broken rule (if it's one of ours).
    message = _CONFLICTS.get(violated_constraint(exc) or "")
    # If found...
    if message:
        # ...answer 409 with it.
        raise ConflictError(message) from exc
    # Otherwise re-raise the original error.
    raise exc


# Database row -> domain BotConfigVersion.
def _to_domain(row: BotConfigVersionRow) -> BotConfigVersion:
    # Build the domain object from:
    return BotConfigVersion(
        # id,
        id=row.id,
        # tenant,
        tenant_id=row.tenant_id,
        # bot,
        bot_id=row.bot_id,
        # version number,
        version=row.version,
        # status (text -> ConfigStatus),
        status=ConfigStatus(row.status),
        # config (JSON -> BotConfig),
        config=config_from_json(row.config),
        # who saved it,
        created_by=row.created_by,
        # when.
        created_at=row.created_at,
    )


# Config versions in the database.
class SqlAlchemyBotConfigRepository:
    # Works inside one (tenant-locked) database session.
    def __init__(self, session: AsyncSession) -> None:
        # Remember it.
        self._session = session

    # Helper: the start of a query for one bot's versions.
    def _scope(self, tenant_id: UUID, bot_id: UUID):  # type: ignore[no-untyped-def]
        # 🔒 SELECT versions WHERE tenant matches AND bot matches.
        return select(BotConfigVersionRow).where(
            BotConfigVersionRow.tenant_id == tenant_id, BotConfigVersionRow.bot_id == bot_id
        )

    # The next version number for this bot (highest + 1).
    async def next_version(self, tenant_id: UUID, bot_id: UUID) -> int:
        # A concurrent save producing the same number hits UNIQUE(bot_id, version) -> retry.
        current = await self._session.scalar(
            # SELECT max(version) (or 0 if none) WHERE tenant and bot match.
            select(func.coalesce(func.max(BotConfigVersionRow.version), 0)).where(
                BotConfigVersionRow.tenant_id == tenant_id, BotConfigVersionRow.bot_id == bot_id
            )
        )
        # The next number: highest + 1.
        return int(current or 0) + 1

    # Insert a new version.
    async def add(self, version: BotConfigVersion) -> None:
        # Add a new row to the session:
        self._session.add(
            # a bot_config_versions row with
            BotConfigVersionRow(
                # its id,
                id=version.id,
                # 🔒 its tenant,
                tenant_id=version.tenant_id,
                # its bot,
                bot_id=version.bot_id,
                # its number,
                version=version.version,
                # its status as text,
                status=version.status.value,
                # its config as JSON,
                config=config_to_json(version.config),
                # who saved it,
                created_by=version.created_by,
                # when.
                created_at=version.created_at,
            )
        )
        # Try to...
        try:
            # ...send the INSERT now so rule violations show up here.
            await self._session.flush()
        # A rule was broken:
        except IntegrityError as exc:
            # 409 for our known races, re-raise anything else.
            _conflict_or_raise(exc)

    # Change a version's status (draft/published/archived).
    async def update_status(self, version: BotConfigVersion) -> None:
        # The partial unique index fires on the UPDATE itself (concurrent publish).
        try:
            # Run:
            await self._session.execute(
                # UPDATE bot_config_versions
                update(BotConfigVersionRow)
                # WHERE
                .where(
                    # the id matches
                    BotConfigVersionRow.id == version.id,
                    # 🔒 and the tenant matches
                    BotConfigVersionRow.tenant_id == version.tenant_id,
                )
                # SET the new status.
                .values(status=version.status.value)
            )
        # A rule was broken (e.g. a second 'published'):
        except IntegrityError as exc:
            # 409 or re-raise.
            _conflict_or_raise(exc)

    # One version by number.
    async def get(self, tenant_id: UUID, bot_id: UUID, version: int) -> BotConfigVersion | None:
        # Run and take one result:
        row = await self._session.scalar(
            # this bot's versions WHERE version = the number asked for.
            self._scope(tenant_id, bot_id).where(BotConfigVersionRow.version == version)
        )
        # Domain object, or None.
        return _to_domain(row) if row else None

    # The newest draft, if any.
    async def latest_draft(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        # Run and take one result:
        row = await self._session.scalar(
            # this bot's versions
            self._scope(tenant_id, bot_id)
            # that are drafts
            .where(BotConfigVersionRow.status == ConfigStatus.DRAFT.value)
            # highest number first
            .order_by(BotConfigVersionRow.version.desc())
            # just the first one.
            .limit(1)
        )
        # Domain object, or None.
        return _to_domain(row) if row else None

    # The live version, if any.
    async def published(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        # Run and take one result:
        row = await self._session.scalar(
            # this bot's versions where...
            self._scope(tenant_id, bot_id).where(
                # ...status is 'published' (there's at most one).
                BotConfigVersionRow.status == ConfigStatus.PUBLISHED.value
            )
        )
        # Domain object, or None.
        return _to_domain(row) if row else None

    # The version history.
    async def list_versions(
        self, tenant_id: UUID, bot_id: UUID, limit: int
    ) -> list[BotConfigVersion]:
        # Run and take all results:
        rows = await self._session.scalars(
            # this bot's versions, newest first, at most `limit`.
            self._scope(tenant_id, bot_id).order_by(BotConfigVersionRow.version.desc()).limit(limit)
        )
        # Turn every row into a domain object.
        return [_to_domain(r) for r in rows]

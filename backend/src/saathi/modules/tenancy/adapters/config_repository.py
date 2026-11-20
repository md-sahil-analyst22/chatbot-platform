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

_CONFLICTS = {
    "uq_bot_config_versions_bot_version": "the configuration was saved concurrently; try again",
    "uq_bot_config_versions_one_published": "another publish is in progress; try again",
}


# Duplicate version number or double publish -> 409 conflict.
def _conflict_or_raise(exc: IntegrityError) -> None:
    message = _CONFLICTS.get(violated_constraint(exc) or "")
    if message:
        raise ConflictError(message) from exc
    raise exc


# Database row -> domain BotConfigVersion.
def _to_domain(row: BotConfigVersionRow) -> BotConfigVersion:
    return BotConfigVersion(
        id=row.id,
        tenant_id=row.tenant_id,
        bot_id=row.bot_id,
        version=row.version,
        status=ConfigStatus(row.status),
        config=config_from_json(row.config),
        created_by=row.created_by,
        created_at=row.created_at,
    )


# Config versions in the database.
class SqlAlchemyBotConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _scope(self, tenant_id: UUID, bot_id: UUID):  # type: ignore[no-untyped-def]
        return select(BotConfigVersionRow).where(
            BotConfigVersionRow.tenant_id == tenant_id, BotConfigVersionRow.bot_id == bot_id
        )

    # The next version number for this bot (highest + 1).
    async def next_version(self, tenant_id: UUID, bot_id: UUID) -> int:
        # A concurrent save producing the same number hits UNIQUE(bot_id, version) -> retry.
        current = await self._session.scalar(
            select(func.coalesce(func.max(BotConfigVersionRow.version), 0)).where(
                BotConfigVersionRow.tenant_id == tenant_id, BotConfigVersionRow.bot_id == bot_id
            )
        )
        return int(current or 0) + 1

    # Insert a new version.
    async def add(self, version: BotConfigVersion) -> None:
        self._session.add(
            BotConfigVersionRow(
                id=version.id,
                tenant_id=version.tenant_id,
                bot_id=version.bot_id,
                version=version.version,
                status=version.status.value,
                config=config_to_json(version.config),
                created_by=version.created_by,
                created_at=version.created_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            _conflict_or_raise(exc)

    # Change a version's status (draft/published/archived).
    async def update_status(self, version: BotConfigVersion) -> None:
        # The partial unique index fires on the UPDATE itself (concurrent publish).
        try:
            await self._session.execute(
                update(BotConfigVersionRow)
                .where(
                    BotConfigVersionRow.id == version.id,
                    BotConfigVersionRow.tenant_id == version.tenant_id,
                )
                .values(status=version.status.value)
            )
        except IntegrityError as exc:
            _conflict_or_raise(exc)

    async def get(self, tenant_id: UUID, bot_id: UUID, version: int) -> BotConfigVersion | None:
        row = await self._session.scalar(
            self._scope(tenant_id, bot_id).where(BotConfigVersionRow.version == version)
        )
        return _to_domain(row) if row else None

    # The newest draft, if any.
    async def latest_draft(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        row = await self._session.scalar(
            self._scope(tenant_id, bot_id)
            .where(BotConfigVersionRow.status == ConfigStatus.DRAFT.value)
            .order_by(BotConfigVersionRow.version.desc())
            .limit(1)
        )
        return _to_domain(row) if row else None

    # The live version, if any.
    async def published(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        row = await self._session.scalar(
            self._scope(tenant_id, bot_id).where(
                BotConfigVersionRow.status == ConfigStatus.PUBLISHED.value
            )
        )
        return _to_domain(row) if row else None

    async def list_versions(
        self, tenant_id: UUID, bot_id: UUID, limit: int
    ) -> list[BotConfigVersion]:
        rows = await self._session.scalars(
            self._scope(tenant_id, bot_id).order_by(BotConfigVersionRow.version.desc()).limit(limit)
        )
        return [_to_domain(r) for r in rows]

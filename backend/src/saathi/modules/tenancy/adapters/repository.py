# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The real database code for bots and tenants (fulfils the contracts in
#       ports/repositories.py).
# Safety: 🔒 Every query filters by tenant_id, AND Postgres row-level security checks again
#         (defence in depth).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From sqlalchemy — SQLAlchemy, our database toolkit: delete = builds a DELETE query; select =
#   builds a SELECT query; update = builds an UPDATE query.
from sqlalchemy import delete, select, update

# From sqlalchemy.exc — database errors: IntegrityError = a database rule was broken (e.g.
#   duplicate).
from sqlalchemy.exc import IntegrityError

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncSession =
#   one unit of database work.
from sqlalchemy.ext.asyncio import AsyncSession

# From saathi.modules.tenancy.adapters.orm — the tenancy table classes: BotRow = bots table;
#   TenantRow = tenants table.
from saathi.modules.tenancy.adapters.orm import BotRow, TenantRow

# From saathi.modules.tenancy.domain.entities — the Bot business object: Bot = one chatbot.
from saathi.modules.tenancy.domain.entities import Bot

# From saathi.platform.db.errors — reads which database rule was broken: violated_constraint =
#   name of the broken rule.
from saathi.platform.db.errors import violated_constraint

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data;
#   NotFoundError = 404 not found.
from saathi.platform.errors import ConflictError, NotFoundError

# The name of the database rule 'bot names are unique per tenant'.
_DUPLICATE_NAME = "uq_bots_tenant_name"


# Turn a duplicate-name database error into a friendly 409 conflict.
def _conflict_or_raise(exc: IntegrityError) -> None:
    # If the broken rule is the duplicate-name rule...
    if violated_constraint(exc) == _DUPLICATE_NAME:
        # ...answer 409 with a friendly message.
        raise ConflictError("a bot with this name already exists") from exc
    # Any other database error: let it continue upwards unchanged.
    raise exc


# Bots, stored in the `bots` table.
class SqlAlchemyBotRepository:
    """Implements BotRepository. The session must come from tenant_session() (RLS bound)."""

    # Each repository works inside one (tenant-locked) database session.
    def __init__(self, session: AsyncSession) -> None:
        # Remember it.
        self._session = session

    # Insert a new bot.
    async def add(self, bot: Bot) -> None:
        # Add a new row to the session:
        self._session.add(
            # a bots-table row with
            BotRow(
                # the bot's id,
                id=bot.id,
                # 🔒 its tenant,
                tenant_id=bot.tenant_id,
                # its name,
                name=bot.name,
                # its persona,
                persona=bot.persona,
                # its languages (as a list for Postgres),
                languages=list(bot.languages),
                # its widget key,
                public_key=bot.public_key,
                # and its settings (as a plain dict).
                settings=dict(bot.settings),
            )
        )
        # Try to...
        try:
            # ...send the INSERT to the database now (so rule violations show up here).
            await self._session.flush()
        # A database rule was broken:
        except IntegrityError as exc:
            # turn a duplicate name into 409, re-raise anything else.
            _conflict_or_raise(exc)

    # Save changes to an existing bot.
    async def update(self, bot: Bot) -> None:
        # Try to...
        try:
            # ...run:
            result = await self._session.execute(
                # UPDATE bots
                update(BotRow)
                # 🔒 WHERE id matches AND tenant matches
                .where(BotRow.id == bot.id, BotRow.tenant_id == bot.tenant_id)
                # SET
                .values(
                    # name,
                    name=bot.name,
                    # persona,
                    persona=bot.persona,
                    # languages,
                    languages=list(bot.languages),
                    # settings.
                    settings=dict(bot.settings),
                )
            )
        # A database rule was broken (e.g. duplicate name):
        except IntegrityError as exc:
            # 409 or re-raise.
            _conflict_or_raise(exc)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # CursorResult for UPDATE
            # No row changed: 404.
            raise NotFoundError("bot not found")

    # Delete; returns False if nothing was found.
    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        # Run:
        result = await self._session.execute(
            # 🔒 DELETE FROM bots WHERE id matches AND tenant matches.
            delete(BotRow).where(BotRow.id == bot_id, BotRow.tenant_id == tenant_id)
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]  # CursorResult for DELETE

    # One bot, or None.
    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None:
        # Run and take the single result:
        row = await self._session.scalar(
            # 🔒 SELECT the bot WHERE id matches AND tenant matches.
            select(BotRow).where(BotRow.id == bot_id, BotRow.tenant_id == tenant_id)
        )
        # Turn the row into a Bot, or None if nothing was found.
        return self._to_domain(row) if row is not None else None

    # All bots of a tenant, newest first.
    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]:
        # Run and take all results:
        rows = await self._session.scalars(
            # SELECT bots
            select(BotRow)
            # 🔒 WHERE tenant matches
            .where(BotRow.tenant_id == tenant_id)
            # newest first
            .order_by(BotRow.created_at.desc())
            # at most `limit` rows.
            .limit(limit)
        )
        # Turn every row into a Bot.
        return [self._to_domain(r) for r in rows]

    # A static method doesn't need `self`.
    @staticmethod
    # Database row -> domain Bot object.
    def _to_domain(row: BotRow) -> Bot:
        # Build a Bot (its rules are checked again) from:
        return Bot(
            # the id,
            id=row.id,
            # the tenant,
            tenant_id=row.tenant_id,
            # the name,
            name=row.name,
            # the persona,
            persona=row.persona,
            # the languages (as a tuple),
            languages=tuple(row.languages),
            # the widget key,
            public_key=row.public_key,
            # the settings.
            settings=row.settings,
        )


# Reads tenant facts (plan).
class SqlAlchemyTenantRepository:
    # Works inside one database session.
    def __init__(self, session: AsyncSession) -> None:
        # Remember it.
        self._session = session

    # The tenant's plan.
    async def get_plan(self, tenant_id: UUID) -> str | None:
        # Run and take the single value:
        plan: str | None = await self._session.scalar(
            # SELECT plan FROM tenants WHERE id matches.
            select(TenantRow.plan).where(TenantRow.id == tenant_id)
        )
        # Return it (None if not found).
        return plan

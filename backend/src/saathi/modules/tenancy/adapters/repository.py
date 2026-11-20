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

_DUPLICATE_NAME = "uq_bots_tenant_name"


# Turn a duplicate-name database error into a friendly 409 conflict.
def _conflict_or_raise(exc: IntegrityError) -> None:
    if violated_constraint(exc) == _DUPLICATE_NAME:
        raise ConflictError("a bot with this name already exists") from exc
    raise exc


# Bots, stored in the `bots` table.
class SqlAlchemyBotRepository:
    """Implements BotRepository. The session must come from tenant_session() (RLS bound)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # Insert a new bot.
    async def add(self, bot: Bot) -> None:
        self._session.add(
            BotRow(
                id=bot.id,
                tenant_id=bot.tenant_id,
                name=bot.name,
                persona=bot.persona,
                languages=list(bot.languages),
                public_key=bot.public_key,
                settings=dict(bot.settings),
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            _conflict_or_raise(exc)

    # Save changes to an existing bot.
    async def update(self, bot: Bot) -> None:
        try:
            result = await self._session.execute(
                update(BotRow)
                .where(BotRow.id == bot.id, BotRow.tenant_id == bot.tenant_id)
                .values(
                    name=bot.name,
                    persona=bot.persona,
                    languages=list(bot.languages),
                    settings=dict(bot.settings),
                )
            )
        except IntegrityError as exc:
            _conflict_or_raise(exc)
        if result.rowcount == 0:  # type: ignore[attr-defined]  # CursorResult for UPDATE
            raise NotFoundError("bot not found")

    # Delete; returns False if nothing was found.
    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        result = await self._session.execute(
            delete(BotRow).where(BotRow.id == bot_id, BotRow.tenant_id == tenant_id)
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]  # CursorResult for DELETE

    # One bot, or None.
    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None:
        row = await self._session.scalar(
            select(BotRow).where(BotRow.id == bot_id, BotRow.tenant_id == tenant_id)
        )
        return self._to_domain(row) if row is not None else None

    # All bots of a tenant, newest first.
    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]:
        rows = await self._session.scalars(
            select(BotRow)
            .where(BotRow.tenant_id == tenant_id)
            .order_by(BotRow.created_at.desc())
            .limit(limit)
        )
        return [self._to_domain(r) for r in rows]

    @staticmethod
    # Database row -> domain Bot object.
    def _to_domain(row: BotRow) -> Bot:
        return Bot(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            persona=row.persona,
            languages=tuple(row.languages),
            public_key=row.public_key,
            settings=row.settings,
        )


# Reads tenant facts (plan).
class SqlAlchemyTenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_plan(self, tenant_id: UUID) -> str | None:
        plan: str | None = await self._session.scalar(
            select(TenantRow.plan).where(TenantRow.id == tenant_id)
        )
        return plan

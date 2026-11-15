from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from saathi.modules.tenancy.adapters.orm import BotRow, TenantRow
from saathi.modules.tenancy.domain.entities import Bot
from saathi.platform.db.errors import violated_constraint
from saathi.platform.errors import ConflictError, NotFoundError

_DUPLICATE_NAME = "uq_bots_tenant_name"


def _conflict_or_raise(exc: IntegrityError) -> None:
    if violated_constraint(exc) == _DUPLICATE_NAME:
        raise ConflictError("a bot with this name already exists") from exc
    raise exc


class SqlAlchemyBotRepository:
    """Implements BotRepository. The session must come from tenant_session() (RLS bound)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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

    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        result = await self._session.execute(
            delete(BotRow).where(BotRow.id == bot_id, BotRow.tenant_id == tenant_id)
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]  # CursorResult for DELETE

    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None:
        row = await self._session.scalar(
            select(BotRow).where(BotRow.id == bot_id, BotRow.tenant_id == tenant_id)
        )
        return self._to_domain(row) if row is not None else None

    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]:
        rows = await self._session.scalars(
            select(BotRow)
            .where(BotRow.tenant_id == tenant_id)
            .order_by(BotRow.created_at.desc())
            .limit(limit)
        )
        return [self._to_domain(r) for r in rows]

    @staticmethod
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


class SqlAlchemyTenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_plan(self, tenant_id: UUID) -> str | None:
        plan: str | None = await self._session.scalar(
            select(TenantRow.plan).where(TenantRow.id == tenant_id)
        )
        return plan

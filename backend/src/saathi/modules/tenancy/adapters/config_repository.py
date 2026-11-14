"""SQLAlchemy implementation of BotConfigRepository. Session must be tenant-bound (RLS)."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from saathi.modules.tenancy.adapters.config_mapper import config_from_json, config_to_json
from saathi.modules.tenancy.adapters.orm import BotConfigVersionRow
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion, ConfigStatus


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


class SqlAlchemyBotConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _scope(self, tenant_id: UUID, bot_id: UUID):  # type: ignore[no-untyped-def]
        return select(BotConfigVersionRow).where(
            BotConfigVersionRow.tenant_id == tenant_id, BotConfigVersionRow.bot_id == bot_id
        )

    async def next_version(self, tenant_id: UUID, bot_id: UUID) -> int:
        # A concurrent save producing the same number hits UNIQUE(bot_id, version) -> retry.
        current = await self._session.scalar(
            select(func.coalesce(func.max(BotConfigVersionRow.version), 0)).where(
                BotConfigVersionRow.tenant_id == tenant_id, BotConfigVersionRow.bot_id == bot_id
            )
        )
        return int(current or 0) + 1

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
        await self._session.flush()

    async def update_status(self, version: BotConfigVersion) -> None:
        await self._session.execute(
            update(BotConfigVersionRow)
            .where(
                BotConfigVersionRow.id == version.id,
                BotConfigVersionRow.tenant_id == version.tenant_id,
            )
            .values(status=version.status.value)
        )
        await self._session.flush()

    async def get(self, tenant_id: UUID, bot_id: UUID, version: int) -> BotConfigVersion | None:
        row = await self._session.scalar(
            self._scope(tenant_id, bot_id).where(BotConfigVersionRow.version == version)
        )
        return _to_domain(row) if row else None

    async def latest_draft(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        row = await self._session.scalar(
            self._scope(tenant_id, bot_id)
            .where(BotConfigVersionRow.status == ConfigStatus.DRAFT.value)
            .order_by(BotConfigVersionRow.version.desc())
            .limit(1)
        )
        return _to_domain(row) if row else None

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

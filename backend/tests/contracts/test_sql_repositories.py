"""SQL repositories pass the SAME contract suites as the in-memory fakes (R35), on real Postgres.

These run as the schema owner, so they prove the repositories' own tenant filters (R15, defence
in depth). RLS for the app role is proven separately in tests/security/test_tenant_isolation.py.

The contracts use random tenant/bot ids; the seeding wrappers only insert the parent rows the
foreign keys need, then call the real repository unchanged.
"""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from tests.contracts.test_bot_config_repository_contract import BotConfigRepositoryContract
from tests.contracts.test_bot_repository_contract import BotRepositoryContract
from tests.db_fixtures import requires_db

from saathi.modules.tenancy.adapters.config_repository import SqlAlchemyBotConfigRepository
from saathi.modules.tenancy.adapters.repository import SqlAlchemyBotRepository
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion
from saathi.modules.tenancy.domain.entities import Bot
from saathi.modules.tenancy.ports.repositories import BotConfigRepository, BotRepository

pytestmark = [pytest.mark.integration, requires_db]


async def _ensure_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text("INSERT INTO tenants (id, name) VALUES (:id, 'contract') ON CONFLICT DO NOTHING"),
        {"id": tenant_id},
    )


class _SeedingBotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SqlAlchemyBotRepository(session)

    async def add(self, bot: Bot) -> None:
        await _ensure_tenant(self._session, bot.tenant_id)
        await self._repo.add(bot)

    async def update(self, bot: Bot) -> None:
        await _ensure_tenant(self._session, bot.tenant_id)
        await self._repo.update(bot)

    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        return await self._repo.delete(tenant_id, bot_id)

    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None:
        return await self._repo.get(tenant_id, bot_id)

    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]:
        return await self._repo.list_for_tenant(tenant_id, limit)


class _SeedingConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SqlAlchemyBotConfigRepository(session)

    async def _ensure_bot(self, tenant_id: UUID, bot_id: UUID) -> None:
        await _ensure_tenant(self._session, tenant_id)
        await self._session.execute(
            text(
                "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                "VALUES (:id, :t, :name, ARRAY['en'], :pk) ON CONFLICT DO NOTHING"
            ),
            {"id": bot_id, "t": tenant_id, "name": str(bot_id), "pk": f"pk_{uuid4().hex}"},
        )

    async def add(self, version: BotConfigVersion) -> None:
        await self._ensure_bot(version.tenant_id, version.bot_id)
        await self._repo.add(version)

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]  # read methods pass through
        return getattr(self._repo, name)


class _OwnerSession:
    """One transaction per test, always rolled back."""

    session: AsyncSession

    @pytest.fixture(autouse=True)
    async def _session(self, owner_engine: AsyncEngine) -> AsyncIterator[None]:
        self.session = AsyncSession(owner_engine, expire_on_commit=False)
        await self.session.begin()
        yield
        await self.session.rollback()
        await self.session.close()


class TestSqlAlchemyBotRepository(_OwnerSession, BotRepositoryContract):
    def make(self) -> BotRepository:
        return _SeedingBotRepository(self.session)


class TestSqlAlchemyBotConfigRepository(_OwnerSession, BotConfigRepositoryContract):
    def make(self) -> BotConfigRepository:
        return _SeedingConfigRepository(self.session)  # type: ignore[return-value]

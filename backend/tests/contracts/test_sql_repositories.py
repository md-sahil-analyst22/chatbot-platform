# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The REAL database repositories pass the same rules as the fakes, on real
#                Postgres.
# How to run: make test-db (needs a throwaway real Postgres - never Supabase; see
#             docs/runbooks/local-setup.md). Skipped otherwise.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQL repositories pass the SAME contract suites as the in-memory fakes (R35), on real Postgres.

These run as the schema owner, so they prove the repositories' own tenant filters (R15, defence
in depth). RLS for the app role is proven separately in tests/security/test_tenant_isolation.py.

The contracts use random tenant/bot ids; the seeding wrappers only insert the parent rows the
foreign keys need, then call the real repository unchanged.
"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# pytest — the test framework.
import pytest

# From sqlalchemy — SQLAlchemy, our database toolkit: text = a raw SQL snippet.
from sqlalchemy import text

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncEngine =
#   the async connection pool; AsyncSession = one unit of database work.
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

# From tests.contracts.test_bot_config_repository_contract — shared config-store test rules:
#   BotConfigRepositoryContract = the shared config-store tests.
from tests.contracts.test_bot_config_repository_contract import BotConfigRepositoryContract

# From tests.contracts.test_bot_repository_contract — shared bot-store test rules:
#   BotRepositoryContract = the shared bot-store tests.
from tests.contracts.test_bot_repository_contract import BotRepositoryContract

# From tests.db_fixtures — real-Postgres test helpers: requires_db = skips the test when no real
#   Postgres is available.
from tests.db_fixtures import requires_db

# From saathi.modules.tenancy.adapters.config_repository — database code for config versions:
#   SqlAlchemyBotConfigRepository = config versions in the database.
from saathi.modules.tenancy.adapters.config_repository import SqlAlchemyBotConfigRepository

# From saathi.modules.tenancy.adapters.repository — database code for bots and tenants:
#   SqlAlchemyBotRepository = bots in the database.
from saathi.modules.tenancy.adapters.repository import SqlAlchemyBotRepository

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfigVersion = one saved version.
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion

# From saathi.modules.tenancy.domain.entities — the Bot business object: Bot = one chatbot.
from saathi.modules.tenancy.domain.entities import Bot

# From saathi.modules.tenancy.ports.repositories — tenancy storage contracts:
#   BotConfigRepository = contract: store config versions; BotRepository = contract: store bots.
from saathi.modules.tenancy.ports.repositories import BotConfigRepository, BotRepository

# Every test in this file is an integration test and needs the real database.
pytestmark = [pytest.mark.integration, requires_db]


# Helper: make sure a tenant row exists (the bot table requires one).
async def _ensure_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    # Run:
    await session.execute(
        # insert a tenant, or do nothing if it already exists,
        text("INSERT INTO tenants (id, name) VALUES (:id, 'contract') ON CONFLICT DO NOTHING"),
        # with this id.
        {"id": tenant_id},
    )


# Wraps the real bot repository so the shared contract tests can use random tenants.
class _SeedingBotRepository:
    # Built with an owner session.
    def __init__(self, session: AsyncSession) -> None:
        # Remember the session.
        self._session = session
        # The real repository being tested.
        self._repo = SqlAlchemyBotRepository(session)

    # Save a bot:
    async def add(self, bot: Bot) -> None:
        # create its tenant first if needed,
        await _ensure_tenant(self._session, bot.tenant_id)
        # then use the real repository.
        await self._repo.add(bot)

    # Save changes:
    async def update(self, bot: Bot) -> None:
        # create the tenant if needed (the hijack test uses a new one),
        await _ensure_tenant(self._session, bot.tenant_id)
        # then use the real repository.
        await self._repo.update(bot)

    # Delete:
    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        # straight to the real repository.
        return await self._repo.delete(tenant_id, bot_id)

    # Read one:
    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None:
        # straight to the real repository.
        return await self._repo.get(tenant_id, bot_id)

    # List:
    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]:
        # straight to the real repository.
        return await self._repo.list_for_tenant(tenant_id, limit)


# Wraps the real config repository so the contract tests can use random tenants and bots.
class _SeedingConfigRepository:
    # Built with an owner session.
    def __init__(self, session: AsyncSession) -> None:
        # Remember the session.
        self._session = session
        # The real repository being tested.
        self._repo = SqlAlchemyBotConfigRepository(session)

    # Helper: make sure the tenant and the bot exist.
    async def _ensure_bot(self, tenant_id: UUID, bot_id: UUID) -> None:
        # The tenant first,
        await _ensure_tenant(self._session, tenant_id)
        # then run:
        await self._session.execute(
            # insert a bot (or do nothing if it exists)
            text(
                "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                "VALUES (:id, :t, :name, ARRAY['en'], :pk) ON CONFLICT DO NOTHING"
            ),
            # with this id, tenant, a name and a random widget key.
            {"id": bot_id, "t": tenant_id, "name": str(bot_id), "pk": f"pk_{uuid4().hex}"},
        )

    # Save a version:
    async def add(self, version: BotConfigVersion) -> None:
        # create its tenant and bot first if needed,
        await self._ensure_bot(version.tenant_id, version.bot_id)
        # then use the real repository.
        await self._repo.add(version)

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]  # read methods pass through
        # Any other method (get, published...) goes straight to the real repository.
        return getattr(self._repo, name)


# Gives each test a database session as the table owner, undone afterwards.
class _OwnerSession:
    """One transaction per test, always rolled back."""

    # The session for the current test.
    session: AsyncSession

    # A fixture that runs automatically for every test in subclasses:
    @pytest.fixture(autouse=True)
    # (needs the owner engine, which empties the tables first)
    async def _session(self, owner_engine: AsyncEngine) -> AsyncIterator[None]:
        # Open a session.
        self.session = AsyncSession(owner_engine, expire_on_commit=False)
        # Start a transaction.
        await self.session.begin()
        # Run the test.
        yield
        # Undo everything the test did.
        await self.session.rollback()
        # Close the session.
        await self.session.close()


# Run the bot contract against real Postgres.
class TestSqlAlchemyBotRepository(_OwnerSession, BotRepositoryContract):
    # Which implementation:
    def make(self) -> BotRepository:
        # the real repository (wrapped).
        return _SeedingBotRepository(self.session)


# Run the config contract against real Postgres.
class TestSqlAlchemyBotConfigRepository(_OwnerSession, BotConfigRepositoryContract):
    # Which implementation:
    def make(self) -> BotConfigRepository:
        return _SeedingConfigRepository(self.session)  # type: ignore[return-value]

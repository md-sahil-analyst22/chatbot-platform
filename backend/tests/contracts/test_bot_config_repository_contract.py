# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every config-version store must follow (fake and real must behave the
#                same).
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""BotConfigRepository contract. The SQL implementation runs it on real Postgres (tests/db/)."""

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: NOW = a fixed time for tests;
#   make_config = builds a test config.
from tests.fakes.builders import NOW, make_config

# From tests.fakes.in_memory — in-memory stand-ins for the database stores:
#   InMemoryBotConfigRepository = config versions in a dict.
from tests.fakes.in_memory import InMemoryBotConfigRepository

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfigVersion = one saved version; ConfigStatus = draft/published/archived.
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion, ConfigStatus

# From saathi.modules.tenancy.ports.repositories — tenancy storage contracts:
#   BotConfigRepository = contract: store config versions.
from saathi.modules.tenancy.ports.repositories import BotConfigRepository

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data.
from saathi.platform.errors import ConflictError


# Helper: a config version for (tenant, bot, number, status).
def _v(tenant, bot, n, status=ConfigStatus.DRAFT) -> BotConfigVersion:  # type: ignore[no-untyped-def]
    # Build it with a test config, author 'u' and the fixed time.
    return BotConfigVersion(uuid4(), tenant, bot, n, status, make_config(), "u", NOW)


# The rules EVERY config-version storage must follow.
class BotConfigRepositoryContract:
    # Each concrete test class below says which implementation to test by overriding make().
    def make(self) -> BotConfigRepository:
        # The base class itself has no implementation.
        raise NotImplementedError

    # Version numbers count up separately for each bot.
    async def test_versions_increment_per_bot(self) -> None:
        # A storage, a tenant and a bot.
        repo, t, b = self.make(), uuid4(), uuid4()
        # No versions yet: next is 1.
        assert await repo.next_version(t, b) == 1
        # Save version 1.
        await repo.add(_v(t, b, 1))
        # Next is 2.
        assert await repo.next_version(t, b) == 2
        # Another bot still starts at 1.
        assert await repo.next_version(t, uuid4()) == 1

    # Find the newest draft and the live version.
    async def test_latest_draft_and_published(self) -> None:
        # A storage, tenant and bot.
        repo, t, b = self.make(), uuid4(), uuid4()
        # Version 1, published.
        await repo.add(_v(t, b, 1, ConfigStatus.PUBLISHED))
        # Version 2, draft.
        await repo.add(_v(t, b, 2))
        # Version 3, draft.
        await repo.add(_v(t, b, 3))
        assert (await repo.latest_draft(t, b)).version == 3  # type: ignore[union-attr]
        assert (await repo.published(t, b)).version == 1  # type: ignore[union-attr]
        # History, newest first, limited to 2.
        assert [v.version for v in await repo.list_versions(t, b, 2)] == [3, 2]

    # 🔒 Another tenant sees nothing.
    async def test_other_tenant_sees_nothing(self) -> None:
        # A storage, tenant and bot.
        repo, t, b = self.make(), uuid4(), uuid4()
        # A published version 1.
        await repo.add(_v(t, b, 1, ConfigStatus.PUBLISHED))
        # Some other tenant.
        other = uuid4()
        # No live version for them.
        assert await repo.published(other, b) is None
        # No version 1 for them.
        assert await repo.get(other, b, 1) is None
        # No history for them.
        assert await repo.list_versions(other, b, 10) == []

    # Saving the same version number twice conflicts.
    async def test_same_version_number_twice_conflicts(self) -> None:
        # A storage, tenant and bot.
        repo, t, b = self.make(), uuid4(), uuid4()
        # Save version 1.
        await repo.add(_v(t, b, 1))
        # Expect ConflictError from the next line:
        with pytest.raises(ConflictError):
            await repo.add(_v(t, b, 1))  # a concurrent save picked the same number

    # 🔒 Only one version may be live at a time.
    async def test_second_published_version_conflicts(self) -> None:
        # A storage, tenant and bot.
        repo, t, b = self.make(), uuid4(), uuid4()
        # Version 1, published.
        await repo.add(_v(t, b, 1, ConfigStatus.PUBLISHED))
        # Version 2, draft...
        draft = _v(t, b, 2)
        # ...saved.
        await repo.add(draft)
        # Expect ConflictError from the next line:
        with pytest.raises(ConflictError):
            await repo.update_status(draft.published())  # without archiving v1 first


# Run all the rules above against the in-memory fake.
class TestInMemoryBotConfigRepository(BotConfigRepositoryContract):
    # Which implementation:
    def make(self) -> BotConfigRepository:
        # the fake.
        return InMemoryBotConfigRepository()

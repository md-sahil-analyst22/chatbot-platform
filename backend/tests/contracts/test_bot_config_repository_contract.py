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


def _v(tenant, bot, n, status=ConfigStatus.DRAFT) -> BotConfigVersion:  # type: ignore[no-untyped-def]
    return BotConfigVersion(uuid4(), tenant, bot, n, status, make_config(), "u", NOW)


class BotConfigRepositoryContract:
    def make(self) -> BotConfigRepository:
        raise NotImplementedError

    async def test_versions_increment_per_bot(self) -> None:
        repo, t, b = self.make(), uuid4(), uuid4()
        assert await repo.next_version(t, b) == 1
        await repo.add(_v(t, b, 1))
        assert await repo.next_version(t, b) == 2
        assert await repo.next_version(t, uuid4()) == 1

    async def test_latest_draft_and_published(self) -> None:
        repo, t, b = self.make(), uuid4(), uuid4()
        await repo.add(_v(t, b, 1, ConfigStatus.PUBLISHED))
        await repo.add(_v(t, b, 2))
        await repo.add(_v(t, b, 3))
        assert (await repo.latest_draft(t, b)).version == 3  # type: ignore[union-attr]
        assert (await repo.published(t, b)).version == 1  # type: ignore[union-attr]
        assert [v.version for v in await repo.list_versions(t, b, 2)] == [3, 2]

    async def test_other_tenant_sees_nothing(self) -> None:
        repo, t, b = self.make(), uuid4(), uuid4()
        await repo.add(_v(t, b, 1, ConfigStatus.PUBLISHED))
        other = uuid4()
        assert await repo.published(other, b) is None
        assert await repo.get(other, b, 1) is None
        assert await repo.list_versions(other, b, 10) == []

    async def test_same_version_number_twice_conflicts(self) -> None:
        repo, t, b = self.make(), uuid4(), uuid4()
        await repo.add(_v(t, b, 1))
        with pytest.raises(ConflictError):
            await repo.add(_v(t, b, 1))  # a concurrent save picked the same number

    async def test_second_published_version_conflicts(self) -> None:
        repo, t, b = self.make(), uuid4(), uuid4()
        await repo.add(_v(t, b, 1, ConfigStatus.PUBLISHED))
        draft = _v(t, b, 2)
        await repo.add(draft)
        with pytest.raises(ConflictError):
            await repo.update_status(draft.published())  # without archiving v1 first


class TestInMemoryBotConfigRepository(BotConfigRepositoryContract):
    def make(self) -> BotConfigRepository:
        return InMemoryBotConfigRepository()

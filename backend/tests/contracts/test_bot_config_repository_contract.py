"""BotConfigRepository contract. P1.6 adds the SQL implementation (real Postgres)."""

from uuid import uuid4

from tests.fakes.builders import NOW, make_config
from tests.fakes.in_memory import InMemoryBotConfigRepository

from saathi.modules.tenancy.domain.bot_config import BotConfigVersion, ConfigStatus
from saathi.modules.tenancy.ports.repositories import BotConfigRepository


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


class TestInMemoryBotConfigRepository(BotConfigRepositoryContract):
    def make(self) -> BotConfigRepository:
        return InMemoryBotConfigRepository()

"""BotRepository contract. P1.6 adds TestSqlAlchemyBotRepository (integration, real Postgres)."""

from uuid import uuid4

from tests.fakes.builders import make_bot
from tests.fakes.in_memory import InMemoryBotRepository

from saathi.modules.tenancy.ports.repositories import BotRepository


class BotRepositoryContract:
    def make(self) -> BotRepository:
        raise NotImplementedError

    async def test_add_then_get_round_trip(self) -> None:
        repo, bot = self.make(), make_bot()
        await repo.add(bot)
        assert await repo.get(bot.tenant_id, bot.id) == bot

    async def test_other_tenant_cannot_read(self) -> None:
        repo, bot = self.make(), make_bot()
        await repo.add(bot)
        assert await repo.get(uuid4(), bot.id) is None

    async def test_list_only_returns_own_tenant(self) -> None:
        repo, mine, theirs = self.make(), make_bot(), make_bot()
        await repo.add(mine)
        await repo.add(theirs)
        assert await repo.list_for_tenant(mine.tenant_id, 10) == [mine]

    async def test_missing_returns_none(self) -> None:
        assert await self.make().get(uuid4(), uuid4()) is None


class TestInMemoryBotRepository(BotRepositoryContract):
    def make(self) -> BotRepository:
        return InMemoryBotRepository()

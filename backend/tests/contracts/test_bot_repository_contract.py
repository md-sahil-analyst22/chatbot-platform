"""BotRepository contract. The SQL implementation runs it on real Postgres (tests/db/)."""

from dataclasses import fields
from typing import Any
from uuid import uuid4

import pytest
from tests.fakes.builders import make_bot
from tests.fakes.in_memory import InMemoryBotRepository

from saathi.modules.tenancy.ports.repositories import BotRepository
from saathi.platform.errors import ConflictError, NotFoundError


def _fields(bot: object) -> dict[str, Any]:
    return {f.name: getattr(bot, f.name) for f in fields(bot)}  # type: ignore[arg-type]


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

    async def test_duplicate_name_in_same_tenant_conflicts(self) -> None:
        repo, first = self.make(), make_bot(name="Mitra")
        await repo.add(first)
        with pytest.raises(ConflictError):
            await repo.add(make_bot(tenant_id=first.tenant_id, name="Mitra"))

    async def test_same_name_in_another_tenant_is_fine(self) -> None:
        repo = self.make()
        await repo.add(make_bot(name="Mitra"))
        await repo.add(make_bot(name="Mitra"))  # different tenant: no conflict

    async def test_update_round_trip(self) -> None:
        repo, bot = self.make(), make_bot(name="Old")
        await repo.add(bot)
        changed = bot.renamed("New").with_languages(("hi", "bn")).with_settings({"k": "v"})
        await repo.update(changed)
        assert await repo.get(bot.tenant_id, bot.id) == changed

    async def test_update_to_taken_name_conflicts(self) -> None:
        repo, a = self.make(), make_bot(name="A")
        b = make_bot(tenant_id=a.tenant_id, name="B")
        await repo.add(a)
        await repo.add(b)
        with pytest.raises(ConflictError):
            await repo.update(b.renamed("A"))

    async def test_update_other_tenants_bot_is_not_found(self) -> None:
        repo, bot = self.make(), make_bot()
        await repo.add(bot)
        foreign = make_bot(tenant_id=uuid4(), name=bot.name)
        hijack = type(bot)(**{**_fields(foreign), "id": bot.id})
        with pytest.raises(NotFoundError):
            await repo.update(hijack)
        assert await repo.get(bot.tenant_id, bot.id) == bot

    async def test_delete_only_own_tenant(self) -> None:
        repo, bot = self.make(), make_bot()
        await repo.add(bot)
        assert await repo.delete(uuid4(), bot.id) is False
        assert await repo.get(bot.tenant_id, bot.id) == bot
        assert await repo.delete(bot.tenant_id, bot.id) is True
        assert await repo.get(bot.tenant_id, bot.id) is None


class TestInMemoryBotRepository(BotRepositoryContract):
    def make(self) -> BotRepository:
        return InMemoryBotRepository()

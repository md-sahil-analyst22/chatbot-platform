# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every bot store must follow (fake and real must behave the same).
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""BotRepository contract. The SQL implementation runs it on real Postgres (tests/db/)."""

# From dataclasses — quick classes that mainly hold data: fields = lists a dataclass's fields.
from dataclasses import fields

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: make_bot = builds a test bot.
from tests.fakes.builders import make_bot

# From tests.fakes.in_memory — in-memory stand-ins for the database stores:
#   InMemoryBotRepository = bots in a dict.
from tests.fakes.in_memory import InMemoryBotRepository

# From saathi.modules.tenancy.ports.repositories — tenancy storage contracts: BotRepository =
#   contract: store bots.
from saathi.modules.tenancy.ports.repositories import BotRepository

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data;
#   NotFoundError = 404 not found.
from saathi.platform.errors import ConflictError, NotFoundError


# Helper: a dataclass's fields as a dictionary.
def _fields(bot: object) -> dict[str, Any]:
    # field name -> value.
    return {f.name: getattr(bot, f.name) for f in fields(bot)}  # type: ignore[arg-type]


# The rules EVERY bot storage must follow (the in-memory fake and the real SQL one).
class BotRepositoryContract:
    # Each concrete test class below says which implementation to test by overriding make().
    def make(self) -> BotRepository:
        # The base class itself has no implementation.
        raise NotImplementedError

    # Saving then reading gives the same bot back.
    async def test_add_then_get_round_trip(self) -> None:
        # A storage and a test bot.
        repo, bot = self.make(), make_bot()
        # Save it.
        await repo.add(bot)
        # Read it back: identical.
        assert await repo.get(bot.tenant_id, bot.id) == bot

    # 🔒 Another tenant can't read it.
    async def test_other_tenant_cannot_read(self) -> None:
        # A storage and a bot.
        repo, bot = self.make(), make_bot()
        # Save it.
        await repo.add(bot)
        # Read with a random tenant: nothing.
        assert await repo.get(uuid4(), bot.id) is None

    # 🔒 Listing returns only the asking tenant's bots.
    async def test_list_only_returns_own_tenant(self) -> None:
        # A storage, my bot and someone else's.
        repo, mine, theirs = self.make(), make_bot(), make_bot()
        # Save mine.
        await repo.add(mine)
        # Save theirs.
        await repo.add(theirs)
        # My list contains only mine.
        assert await repo.list_for_tenant(mine.tenant_id, 10) == [mine]

    # Unknown ids give None.
    async def test_missing_returns_none(self) -> None:
        # Read random ids: nothing.
        assert await self.make().get(uuid4(), uuid4()) is None

    # Two bots with the same name in one tenant conflict.
    async def test_duplicate_name_in_same_tenant_conflicts(self) -> None:
        # A storage and a bot named Mitra.
        repo, first = self.make(), make_bot(name="Mitra")
        # Save it.
        await repo.add(first)
        # Expect ConflictError from the next line:
        with pytest.raises(ConflictError):
            # save another 'Mitra' in the same tenant.
            await repo.add(make_bot(tenant_id=first.tenant_id, name="Mitra"))

    # The same name in different tenants is fine.
    async def test_same_name_in_another_tenant_is_fine(self) -> None:
        # A storage.
        repo = self.make()
        # Save 'Mitra' (random tenant).
        await repo.add(make_bot(name="Mitra"))
        await repo.add(make_bot(name="Mitra"))  # different tenant: no conflict

    # Changes are saved and read back exactly.
    async def test_update_round_trip(self) -> None:
        # A storage and a bot named Old.
        repo, bot = self.make(), make_bot(name="Old")
        # Save it.
        await repo.add(bot)
        # Rename it, change languages and settings.
        changed = bot.renamed("New").with_languages(("hi", "bn")).with_settings({"k": "v"})
        # Save the changes.
        await repo.update(changed)
        # Read back: identical to the changed copy.
        assert await repo.get(bot.tenant_id, bot.id) == changed

    # Renaming to a taken name conflicts.
    async def test_update_to_taken_name_conflicts(self) -> None:
        # A storage and bot A.
        repo, a = self.make(), make_bot(name="A")
        # Bot B in the same tenant.
        b = make_bot(tenant_id=a.tenant_id, name="B")
        # Save A.
        await repo.add(a)
        # Save B.
        await repo.add(b)
        # Expect ConflictError from the next line:
        with pytest.raises(ConflictError):
            # rename B to 'A'.
            await repo.update(b.renamed("A"))

    # 🔒 You can't overwrite another tenant's bot by reusing its id.
    async def test_update_other_tenants_bot_is_not_found(self) -> None:
        # A storage and a bot.
        repo, bot = self.make(), make_bot()
        # Save it.
        await repo.add(bot)
        # A bot from another tenant...
        foreign = make_bot(tenant_id=uuid4(), name=bot.name)
        # ...given the same id as ours (an attempted hijack).
        hijack = type(bot)(**{**_fields(foreign), "id": bot.id})
        # Expect NotFoundError from the next line:
        with pytest.raises(NotFoundError):
            # try to save the hijack.
            await repo.update(hijack)
        # Our bot is unchanged.
        assert await repo.get(bot.tenant_id, bot.id) == bot

    # 🔒 Deleting only works inside your own tenant.
    async def test_delete_only_own_tenant(self) -> None:
        # A storage and a bot.
        repo, bot = self.make(), make_bot()
        # Save it.
        await repo.add(bot)
        # Deleting as another tenant does nothing...
        assert await repo.delete(uuid4(), bot.id) is False
        # ...and the bot is still there.
        assert await repo.get(bot.tenant_id, bot.id) == bot
        # Deleting as the owner works...
        assert await repo.delete(bot.tenant_id, bot.id) is True
        # ...and it's gone.
        assert await repo.get(bot.tenant_id, bot.id) is None


# Run all the rules above against the in-memory fake.
class TestInMemoryBotRepository(BotRepositoryContract):
    # Which implementation:
    def make(self) -> BotRepository:
        # the fake.
        return InMemoryBotRepository()

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The use cases for bots: create, list, read, update, delete.
# Pattern: Each method: 1) check the caller's role, 2) do the work through the repository
#          contract. The tenant always comes from the verified caller.
# Called by: api/routes.py.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# secrets — secure random values.
import secrets

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; field = per-field options such as a default empty list.
from dataclasses import dataclass, field

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# From saathi.modules.tenancy.domain.entities — the Bot business object: Bot = one chatbot.
from saathi.modules.tenancy.domain.entities import Bot

# From saathi.modules.tenancy.ports.repositories — tenancy storage contracts: BotRepository =
#   contract: store bots.
from saathi.modules.tenancy.ports.repositories import BotRepository

# From saathi.platform.errors — our error types: NotFoundError = 404 not found.
from saathi.platform.errors import NotFoundError

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; Role = viewer/agent/admin/owner; require_role = stops with 403 if the role is
#   too low.
from saathi.platform.security.auth import Principal, Role, require_role


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# The input needed to create a bot.
class CreateBotCommand:
    # The new bot's name.
    name: str
    # Its personality text.
    persona: str
    # Its languages.
    languages: tuple[str, ...]
    # Extra settings (empty by default).
    settings: dict[str, Any] = field(default_factory=dict)


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# The input for changing a bot; empty fields mean 'leave as is'.
class UpdateBotCommand:
    """Partial update: None means "leave unchanged"."""

    # New name, or None to keep the old one.
    name: str | None = None
    # New persona, or None.
    persona: str | None = None
    # New languages, or None.
    languages: tuple[str, ...] | None = None
    # New settings, or None.
    settings: dict[str, Any] | None = None


# The bot use cases.
class BotService:
    # The bot storage is handed in (database in production, a dict in tests).
    def __init__(self, repo: BotRepository) -> None:
        # Remember it.
        self._repo = repo

    # Admins and owners only.
    async def create_bot(self, principal: Principal, cmd: CreateBotCommand) -> Bot:
        # 🔒 Only admins and owners may create bots.
        require_role(principal, Role.ADMIN)
        # Build the new bot (its own rules are checked right here):
        bot = Bot(
            # a new random id,
            id=uuid4(),
            tenant_id=principal.tenant_id,  # from the token, never from the request body
            # the name,
            name=cmd.name,
            # the persona,
            persona=cmd.persona,
            # the languages,
            languages=cmd.languages,
            # a new random public widget key, e.g. pk_3fQ...
            public_key="pk_" + secrets.token_urlsafe(24),
            # and the extra settings.
            settings=cmd.settings,
        )
        # Save it.
        await self._repo.add(bot)
        # Return the saved bot.
        return bot

    # Anyone in the workspace may list bots.
    async def list_bots(self, principal: Principal, limit: int = 50) -> list[Bot]:
        # Any member may list bots.
        require_role(principal, Role.VIEWER)
        # This tenant's bots, never more than 100 at once.
        return await self._repo.list_for_tenant(principal.tenant_id, min(limit, 100))

    # Missing (or another tenant's) bot -> 404.
    async def get_bot(self, principal: Principal, bot_id: UUID) -> Bot:
        # Any member may read a bot.
        require_role(principal, Role.VIEWER)
        # Look it up inside the caller's tenant only.
        bot = await self._repo.get(principal.tenant_id, bot_id)
        # Not found (or another tenant's):
        if bot is None:
            # 404.
            raise NotFoundError("bot not found")
        # Found: return it.
        return bot

    # Admins and owners only; builds a changed copy of the bot.
    async def update_bot(self, principal: Principal, bot_id: UUID, cmd: UpdateBotCommand) -> Bot:
        # 🔒 Only admins and owners may change bots.
        require_role(principal, Role.ADMIN)
        bot = await self.get_bot(principal, bot_id)  # 404 for another tenant's bot (R29)
        # A new name was given...
        if cmd.name is not None:
            # ...so make a renamed copy.
            bot = bot.renamed(cmd.name)
        # A new persona was given...
        if cmd.persona is not None:
            # ...so make a copy with it.
            bot = bot.with_persona(cmd.persona)
        # New languages were given...
        if cmd.languages is not None:
            # ...so make a copy with them.
            bot = bot.with_languages(cmd.languages)
        # New settings were given...
        if cmd.settings is not None:
            # ...so make a copy with them.
            bot = bot.with_settings(cmd.settings)
        # Save the changed bot.
        await self._repo.update(bot)
        # Return it.
        return bot

    # Admins and owners only.
    async def delete_bot(self, principal: Principal, bot_id: UUID) -> None:
        """Deletes the bot and everything that belongs to it (configs, sources, chats)."""
        # 🔒 Only admins and owners may delete bots.
        require_role(principal, Role.ADMIN)
        # Delete inside the caller's tenant; nothing deleted...
        if not await self._repo.delete(principal.tenant_id, bot_id):
            # ...means 404.
            raise NotFoundError("bot not found")

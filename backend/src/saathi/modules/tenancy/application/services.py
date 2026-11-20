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


@dataclass(frozen=True, slots=True)
# The input needed to create a bot.
class CreateBotCommand:
    name: str
    persona: str
    languages: tuple[str, ...]
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
# The input for changing a bot; empty fields mean 'leave as is'.
class UpdateBotCommand:
    """Partial update: None means "leave unchanged"."""

    name: str | None = None
    persona: str | None = None
    languages: tuple[str, ...] | None = None
    settings: dict[str, Any] | None = None


# The bot use cases.
class BotService:
    def __init__(self, repo: BotRepository) -> None:
        self._repo = repo

    # Admins and owners only.
    async def create_bot(self, principal: Principal, cmd: CreateBotCommand) -> Bot:
        require_role(principal, Role.ADMIN)
        bot = Bot(
            id=uuid4(),
            tenant_id=principal.tenant_id,  # from the token, never from the request body
            name=cmd.name,
            persona=cmd.persona,
            languages=cmd.languages,
            public_key="pk_" + secrets.token_urlsafe(24),
            settings=cmd.settings,
        )
        await self._repo.add(bot)
        return bot

    # Anyone in the workspace may list bots.
    async def list_bots(self, principal: Principal, limit: int = 50) -> list[Bot]:
        require_role(principal, Role.VIEWER)
        return await self._repo.list_for_tenant(principal.tenant_id, min(limit, 100))

    # Missing (or another tenant's) bot -> 404.
    async def get_bot(self, principal: Principal, bot_id: UUID) -> Bot:
        require_role(principal, Role.VIEWER)
        bot = await self._repo.get(principal.tenant_id, bot_id)
        if bot is None:
            raise NotFoundError("bot not found")
        return bot

    # Admins and owners only; builds a changed copy of the bot.
    async def update_bot(self, principal: Principal, bot_id: UUID, cmd: UpdateBotCommand) -> Bot:
        require_role(principal, Role.ADMIN)
        bot = await self.get_bot(principal, bot_id)  # 404 for another tenant's bot (R29)
        if cmd.name is not None:
            bot = bot.renamed(cmd.name)
        if cmd.persona is not None:
            bot = bot.with_persona(cmd.persona)
        if cmd.languages is not None:
            bot = bot.with_languages(cmd.languages)
        if cmd.settings is not None:
            bot = bot.with_settings(cmd.settings)
        await self._repo.update(bot)
        return bot

    # Admins and owners only.
    async def delete_bot(self, principal: Principal, bot_id: UUID) -> None:
        """Deletes the bot and everything that belongs to it (configs, sources, chats)."""
        require_role(principal, Role.ADMIN)
        if not await self._repo.delete(principal.tenant_id, bot_id):
            raise NotFoundError("bot not found")

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The CONTRACTS for saving and loading bots, configs and tenants.
# Why: Business code calls these contracts; the real database code (adapters/) or test fakes
#      fulfil them.
# Note: 🔒 Every method takes tenant_id, so a call can never forget which tenant it serves (R15).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfigVersion = one saved version.
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion

# From saathi.modules.tenancy.domain.entities — the Bot business object: Bot = one chatbot.
from saathi.modules.tenancy.domain.entities import Bot


# Save, change, delete and read bots.
class BotRepository(Protocol):
    """Persistence port. tenant_id is explicit (defence in depth on top of RLS)."""

    # Save a new bot.
    async def add(self, bot: Bot) -> None:
        """Raises ConflictError if the tenant already has a bot with this name."""
        ...

    # Save changes to an existing bot.
    async def update(self, bot: Bot) -> None:
        """Raises ConflictError on a duplicate name, NotFoundError if the bot is gone."""
        ...

    # Delete a bot; True if something was deleted.
    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        """True if a bot was deleted. Its configs, sources, chats... go with it (FK cascade)."""
        ...

    # One bot of this tenant, or None (`...` = contract only, no body).
    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None: ...

    # Up to `limit` bots of this tenant.
    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]: ...


# Read facts about a tenant (today: its plan).
class TenantRepository(Protocol):
    # The tenant's plan name, or None if unknown.
    async def get_plan(self, tenant_id: UUID) -> str | None: ...


# Save and read configuration versions.
class BotConfigRepository(Protocol):
    """Append-only store of configuration versions."""

    # The next free version number for this bot.
    async def next_version(self, tenant_id: UUID, bot_id: UUID) -> int: ...

    # Save a new version.
    async def add(self, version: BotConfigVersion) -> None:
        """Raises ConflictError if that version number was taken concurrently."""
        ...

    # Change the status of a saved version.
    async def update_status(self, version: BotConfigVersion) -> None:
        """Raises ConflictError if it would leave two published versions (concurrent publish)."""
        ...

    # One version by number, or None.
    async def get(self, tenant_id: UUID, bot_id: UUID, version: int) -> BotConfigVersion | None: ...

    # The newest draft, or None.
    async def latest_draft(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None: ...

    # The live version, or None.
    async def published(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None: ...

    # Up to `limit` versions, newest first.
    async def list_versions(
        self, tenant_id: UUID, bot_id: UUID, limit: int
    ) -> list[BotConfigVersion]: ...


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# The result of looking up a widget key: which tenant and which bot.
class PublicBotRef:
    # The tenant that owns the bot.
    tenant_id: UUID
    # The bot.
    bot_id: UUID


# Contract: widget key -> (tenant, bot), or None.
class PublicBotLookup(Protocol):
    """Resolves a widget's public key to its tenant BEFORE any tenant context exists."""

    # Widget key -> (tenant, bot), or None if unknown.
    async def resolve(self, public_key: str) -> PublicBotRef | None: ...

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: A contract for 'something else must react when a bot's configuration is published'.
# Example: when the chunk size changes, every document of the bot must be processed again. That
#   work belongs to the knowledge module, which tenancy may not import (R4), so bootstrap/ plugs
#   in an implementation backed by knowledge.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Publish hook port for the tenancy module."""

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.tenancy.domain.bot_config — configuration: BotConfig = the full settings.
from saathi.modules.tenancy.domain.bot_config import BotConfig


# Contract: react to a publish.
class ConfigPublishedHook(Protocol):
    # Called inside the publish transaction, after the new version became live. `previous` is the
    #   version that was live before (None for the first publish). Implementations must not
    #   send anything outside the database before the commit (use an after-commit list).
    async def on_published(
        self, tenant_id: UUID, bot_id: UUID, previous: BotConfig | None, current: BotConfig
    ) -> None: ...

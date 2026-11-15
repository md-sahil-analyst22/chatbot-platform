from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from saathi.modules.tenancy.domain.bot_config import BotConfigVersion
from saathi.modules.tenancy.domain.entities import Bot


class BotRepository(Protocol):
    """Persistence port. tenant_id is explicit (defence in depth on top of RLS)."""

    async def add(self, bot: Bot) -> None:
        """Raises ConflictError if the tenant already has a bot with this name."""
        ...

    async def update(self, bot: Bot) -> None:
        """Raises ConflictError on a duplicate name, NotFoundError if the bot is gone."""
        ...

    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        """True if a bot was deleted. Its configs, sources, chats... go with it (FK cascade)."""
        ...

    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None: ...

    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]: ...


class TenantRepository(Protocol):
    async def get_plan(self, tenant_id: UUID) -> str | None: ...


class BotConfigRepository(Protocol):
    """Append-only store of configuration versions."""

    async def next_version(self, tenant_id: UUID, bot_id: UUID) -> int: ...

    async def add(self, version: BotConfigVersion) -> None:
        """Raises ConflictError if that version number was taken concurrently."""
        ...

    async def update_status(self, version: BotConfigVersion) -> None:
        """Raises ConflictError if it would leave two published versions (concurrent publish)."""
        ...

    async def get(self, tenant_id: UUID, bot_id: UUID, version: int) -> BotConfigVersion | None: ...

    async def latest_draft(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None: ...

    async def published(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None: ...

    async def list_versions(
        self, tenant_id: UUID, bot_id: UUID, limit: int
    ) -> list[BotConfigVersion]: ...


@dataclass(frozen=True, slots=True)
class PublicBotRef:
    tenant_id: UUID
    bot_id: UUID


class PublicBotLookup(Protocol):
    """Resolves a widget's public key to its tenant BEFORE any tenant context exists."""

    async def resolve(self, public_key: str) -> PublicBotRef | None: ...

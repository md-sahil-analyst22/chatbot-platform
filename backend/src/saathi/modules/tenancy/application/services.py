import secrets
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from saathi.modules.tenancy.domain.entities import Bot
from saathi.modules.tenancy.ports.repositories import BotRepository
from saathi.platform.errors import NotFoundError
from saathi.platform.security.auth import Principal, Role, require_role


@dataclass(frozen=True, slots=True)
class CreateBotCommand:
    name: str
    persona: str
    languages: tuple[str, ...]
    settings: dict[str, Any] = field(default_factory=dict)


class BotService:
    def __init__(self, repo: BotRepository) -> None:
        self._repo = repo

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

    async def list_bots(self, principal: Principal, limit: int = 50) -> list[Bot]:
        require_role(principal, Role.VIEWER)
        return await self._repo.list_for_tenant(principal.tenant_id, min(limit, 100))

    async def get_bot(self, principal: Principal, bot_id: UUID) -> Bot:
        require_role(principal, Role.VIEWER)
        bot = await self._repo.get(principal.tenant_id, bot_id)
        if bot is None:
            raise NotFoundError("bot not found")
        return bot

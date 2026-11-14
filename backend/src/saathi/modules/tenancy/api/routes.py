"""HTTP adapter for the tenancy use cases. Translates DTOs <-> commands/entities only."""

from uuid import UUID

from fastapi import APIRouter, Query, status

from saathi.api.deps import PrincipalDep
from saathi.modules.tenancy.api.deps import BotServiceDep
from saathi.modules.tenancy.api.schemas import BotCreate, BotOut
from saathi.modules.tenancy.application.services import CreateBotCommand
from saathi.modules.tenancy.domain.entities import Bot

router = APIRouter(prefix="/bots", tags=["bots"])


def _out(bot: Bot) -> BotOut:
    return BotOut(
        id=bot.id,
        name=bot.name,
        persona=bot.persona,
        languages=list(bot.languages),
        public_key=bot.public_key,
        settings=dict(bot.settings),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_bot(body: BotCreate, principal: PrincipalDep, service: BotServiceDep) -> BotOut:
    bot = await service.create_bot(
        principal,
        CreateBotCommand(
            name=body.name,
            persona=body.persona,
            languages=tuple(body.languages),
            settings=body.settings,
        ),
    )
    return _out(bot)


@router.get("")
async def list_bots(
    principal: PrincipalDep, service: BotServiceDep, limit: int = Query(default=50, ge=1, le=100)
) -> list[BotOut]:
    return [_out(b) for b in await service.list_bots(principal, limit)]


@router.get("/{bot_id}")
async def get_bot(bot_id: UUID, principal: PrincipalDep, service: BotServiceDep) -> BotOut:
    return _out(await service.get_bot(principal, bot_id))

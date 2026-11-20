# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The web endpoints for bots: /api/v1/bots (create, list, read, update, delete).
# Style: Routes are thin: turn JSON into a command, call BotService, turn the result into JSON.
#        All rules live in the service.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""HTTP adapter for the tenancy use cases. Translates DTOs <-> commands/entities only."""

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From fastapi — the web framework that turns Python functions into web endpoints: APIRouter = a
#   group of related endpoints; Query = rules for a ?query value; Response = the outgoing HTTP
#   response; status = named HTTP status codes.
from fastapi import APIRouter, Query, Response, status

# From saathi.api.deps — shared request helpers: the verified caller, a tenant-locked database
#   session: PrincipalDep = the verified caller.
from saathi.api.deps import PrincipalDep

# From saathi.modules.tenancy.api.deps — builds the tenancy services per request: BotServiceDep
#   = a ready BotService.
from saathi.modules.tenancy.api.deps import BotServiceDep

# From saathi.modules.tenancy.api.schemas — the JSON shapes of the tenancy API: BotCreate =
#   create-bot request body; BotOut = bot response; BotUpdate = update-bot request body.
from saathi.modules.tenancy.api.schemas import BotCreate, BotOut, BotUpdate

# From saathi.modules.tenancy.application.services — the bot use cases: CreateBotCommand = input
#   for creating a bot; UpdateBotCommand = input for changing a bot.
from saathi.modules.tenancy.application.services import CreateBotCommand, UpdateBotCommand

# From saathi.modules.tenancy.domain.entities — the Bot business object: Bot = one chatbot.
from saathi.modules.tenancy.domain.entities import Bot

router = APIRouter(prefix="/bots", tags=["bots"])


# Domain Bot -> API response.
def _out(bot: Bot) -> BotOut:
    return BotOut(
        id=bot.id,
        name=bot.name,
        persona=bot.persona,
        languages=list(bot.languages),
        public_key=bot.public_key,
        settings=dict(bot.settings),
    )


# POST /api/v1/bots - create a bot.
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


# GET /api/v1/bots - list bots.
@router.get("")
async def list_bots(
    principal: PrincipalDep, service: BotServiceDep, limit: int = Query(default=50, ge=1, le=100)
) -> list[BotOut]:
    return [_out(b) for b in await service.list_bots(principal, limit)]


# GET /api/v1/bots/{id} - one bot.
@router.get("/{bot_id}")
async def get_bot(bot_id: UUID, principal: PrincipalDep, service: BotServiceDep) -> BotOut:
    return _out(await service.get_bot(principal, bot_id))


# PATCH /api/v1/bots/{id} - change a bot.
@router.patch("/{bot_id}")
async def update_bot(
    bot_id: UUID, body: BotUpdate, principal: PrincipalDep, service: BotServiceDep
) -> BotOut:
    bot = await service.update_bot(
        principal,
        bot_id,
        UpdateBotCommand(
            name=body.name,
            persona=body.persona,
            languages=tuple(body.languages) if body.languages is not None else None,
            settings=body.settings,
        ),
    )
    return _out(bot)


# DELETE /api/v1/bots/{id} - delete a bot.
@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(bot_id: UUID, principal: PrincipalDep, service: BotServiceDep) -> Response:
    await service.delete_bot(principal, bot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

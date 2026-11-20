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

# All endpoints below live under /bots (mounted at /api/v1, so /api/v1/bots).
router = APIRouter(prefix="/bots", tags=["bots"])


# Domain Bot -> API response.
def _out(bot: Bot) -> BotOut:
    # Build the response from:
    return BotOut(
        # the id,
        id=bot.id,
        # the name,
        name=bot.name,
        # the persona,
        persona=bot.persona,
        # the languages (as a list),
        languages=list(bot.languages),
        # the widget key,
        public_key=bot.public_key,
        # the settings (as a dict).
        settings=dict(bot.settings),
    )


# POST /api/v1/bots - create a bot.
@router.post("", status_code=status.HTTP_201_CREATED)
# FastAPI checks the body (BotCreate), verifies the caller and builds the service for us.
async def create_bot(body: BotCreate, principal: PrincipalDep, service: BotServiceDep) -> BotOut:
    # Ask the service to create the bot, passing:
    bot = await service.create_bot(
        # the verified caller,
        principal,
        # with a command built from the request body:
        CreateBotCommand(
            # name,
            name=body.name,
            # persona,
            persona=body.persona,
            # languages (list -> tuple),
            languages=tuple(body.languages),
            # settings.
            settings=body.settings,
        ),
    )
    # Answer 201 Created with the new bot.
    return _out(bot)


# GET /api/v1/bots - list bots.
@router.get("")
# `limit` comes from ?limit= (default 50, between 1 and 100).
async def list_bots(
    principal: PrincipalDep, service: BotServiceDep, limit: int = Query(default=50, ge=1, le=100)
) -> list[BotOut]:
    # Get the bots and turn each into a response.
    return [_out(b) for b in await service.list_bots(principal, limit)]


# GET /api/v1/bots/{id} - one bot.
@router.get("/{bot_id}")
# bot_id comes from the URL and must be a valid UUID (else 422).
async def get_bot(bot_id: UUID, principal: PrincipalDep, service: BotServiceDep) -> BotOut:
    # Get the bot (404 if missing) and return it.
    return _out(await service.get_bot(principal, bot_id))


# PATCH /api/v1/bots/{id} - change a bot.
@router.patch("/{bot_id}")
# bot_id from the URL, the body checked as BotUpdate.
async def update_bot(
    bot_id: UUID, body: BotUpdate, principal: PrincipalDep, service: BotServiceDep
) -> BotOut:
    # Ask the service to change the bot:
    bot = await service.update_bot(
        # the verified caller,
        principal,
        # which bot,
        bot_id,
        # and a command built from the body:
        UpdateBotCommand(
            # new name (or None),
            name=body.name,
            # new persona (or None),
            persona=body.persona,
            # new languages as a tuple (or None),
            languages=tuple(body.languages) if body.languages is not None else None,
            # new settings (or None).
            settings=body.settings,
        ),
    )
    # Return the changed bot.
    return _out(bot)


# DELETE /api/v1/bots/{id} - delete a bot.
@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
# bot_id from the URL.
async def delete_bot(bot_id: UUID, principal: PrincipalDep, service: BotServiceDep) -> Response:
    # Delete it (404 if missing).
    await service.delete_bot(principal, bot_id)
    # Answer 204 No Content: success, nothing to send back.
    return Response(status_code=status.HTTP_204_NO_CONTENT)

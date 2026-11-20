# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The Bot Studio endpoints: model options, save draft, list versions, draft, published,
#       publish, rollback.
# Style: Thin: JSON <-> domain objects; all rules live in BotConfigService.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Bot Studio endpoints. Thin: translate DTOs <-> domain, call BotConfigService."""

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From fastapi — the web framework that turns Python functions into web endpoints: APIRouter = a
#   group of related endpoints; Query = rules for a ?query value; status = named HTTP status
#   codes.
from fastapi import APIRouter, Query, status

# From saathi.api.deps — shared request helpers: the verified caller, a tenant-locked database
#   session: PrincipalDep = the verified caller.
from saathi.api.deps import PrincipalDep

# From saathi.modules.tenancy.api.deps — builds the tenancy services per request:
#   BotConfigServiceDep = a ready BotConfigService.
from saathi.modules.tenancy.api.deps import BotConfigServiceDep

# From saathi.modules.tenancy.api.schemas — the JSON shapes of the tenancy API: BotConfigIn =
#   config request body; BotConfigVersionOut = config version response; ModelOptionOut = model
#   option response.
from saathi.modules.tenancy.api.schemas import BotConfigIn, BotConfigVersionOut, ModelOptionOut

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfig = one full configuration; BotConfigVersion = one saved version; Branding = how the
#   widget looks; GenerationSettings = model and answer style; PromptSettings = the tenant's
#   instructions; ResponseStyle = precise/balanced/friendly.
from saathi.modules.tenancy.domain.bot_config import (
    BotConfig,
    BotConfigVersion,
    Branding,
    GenerationSettings,
    PromptSettings,
    ResponseStyle,
)

router = APIRouter(prefix="/bots/{bot_id}/config", tags=["bot-config"])
options_router = APIRouter(tags=["bot-config"])


# Request JSON -> domain BotConfig.
def to_domain(body: BotConfigIn) -> BotConfig:
    p, g, b = body.prompt, body.generation, body.branding
    return BotConfig(
        prompt=PromptSettings(
            persona=p.persona,
            brand_rules=p.brand_rules,
            custom_instructions=p.custom_instructions,
            banned_topics=tuple(p.banned_topics),
        ),
        generation=GenerationSettings(
            model_key=g.model_key,
            style=ResponseStyle(g.style),
            temperature_override=g.temperature_override,
            max_output_tokens=g.max_output_tokens,
        ),
        branding=Branding(
            header_title=b.header_title,
            header_subtitle=b.header_subtitle,
            footer_text=b.footer_text,
            greeting=b.greeting,
            primary_color=b.primary_color,
            launcher_position=b.launcher_position,
            logo_asset_id=b.logo_asset_id,
        ),
    )


# Domain version -> API response.
def to_out(v: BotConfigVersion) -> BotConfigVersionOut:
    c = v.config
    return BotConfigVersionOut.model_validate(
        {
            "version": v.version,
            "status": v.status.value,
            "created_by": v.created_by,
            "created_at": v.created_at,
            "config": {
                "prompt": {
                    "persona": c.prompt.persona,
                    "brand_rules": c.prompt.brand_rules,
                    "custom_instructions": c.prompt.custom_instructions,
                    "banned_topics": list(c.prompt.banned_topics),
                },
                "generation": {
                    "model_key": c.generation.model_key,
                    "style": c.generation.style.value,
                    "temperature_override": c.generation.temperature_override,
                    "max_output_tokens": c.generation.max_output_tokens,
                },
                "branding": {
                    "header_title": c.branding.header_title,
                    "header_subtitle": c.branding.header_subtitle,
                    "footer_text": c.branding.footer_text,
                    "greeting": c.branding.greeting,
                    "primary_color": c.branding.primary_color,
                    "launcher_position": c.branding.launcher_position,
                    "logo_asset_id": c.branding.logo_asset_id,
                },
            },
        }
    )


@options_router.get("/model-options")
# GET the models the caller's plan allows.
async def list_model_options(
    principal: PrincipalDep, service: BotConfigServiceDep
) -> list[ModelOptionOut]:
    return [
        ModelOptionOut(key=o.key, label=o.label) for o in await service.model_options(principal)
    ]


# Save a new draft.
@router.post("/versions", status_code=status.HTTP_201_CREATED)
async def save_draft(
    bot_id: UUID, body: BotConfigIn, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    return to_out(await service.save_draft(principal, bot_id, to_domain(body)))


# Version history.
@router.get("/versions")
async def list_versions(
    bot_id: UUID,
    principal: PrincipalDep,
    service: BotConfigServiceDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[BotConfigVersionOut]:
    return [to_out(v) for v in await service.list_versions(principal, bot_id, limit)]


# Newest draft.
@router.get("/draft")
async def get_draft(
    bot_id: UUID, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    return to_out(await service.get_draft(principal, bot_id))


# Live version.
@router.get("/published")
async def get_published(
    bot_id: UUID, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    return to_out(await service.get_published(principal, bot_id))


# Make a version live.
@router.post("/versions/{version}/publish")
async def publish(
    bot_id: UUID, version: int, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    return to_out(await service.publish(principal, bot_id, version))


# Go back to an old version.
@router.post("/versions/{version}/rollback")
async def rollback(
    bot_id: UUID, version: int, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    return to_out(await service.rollback(principal, bot_id, version))


# Logo upload (P4.13): POST /bots/{bot_id}/branding/logo
#   multipart -> platform.security.uploads.validate_logo (PNG/JPEG/WebP, <= 512 KB, no SVG)
#   -> ObjectStore key "t/{tenant_id}/bots/{bot_id}/logo-{uuid}{ext}" -> returns logo_asset_id

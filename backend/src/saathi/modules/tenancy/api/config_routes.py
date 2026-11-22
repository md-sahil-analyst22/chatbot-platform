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
    RetrievalSettings,
)

# Bot Studio endpoints live under /bots/{bot_id}/config (so /api/v1/bots/<id>/config/...).
router = APIRouter(prefix="/bots/{bot_id}/config", tags=["bot-config"])
# A second group for /model-options, which isn't tied to one bot.
options_router = APIRouter(tags=["bot-config"])


# Request JSON -> domain BotConfig.
def to_domain(body: BotConfigIn) -> BotConfig:
    # Short names for the three parts of the request.
    p, g, b, r = body.prompt, body.generation, body.branding, body.retrieval
    # Build the domain objects (their rules are checked here too):
    return BotConfig(
        # the prompt part:
        prompt=PromptSettings(
            # persona,
            persona=p.persona,
            # brand rules,
            brand_rules=p.brand_rules,
            # custom instructions,
            custom_instructions=p.custom_instructions,
            # banned topics (list -> tuple).
            banned_topics=tuple(p.banned_topics),
        ),
        # The generation part:
        generation=GenerationSettings(
            # model key,
            model_key=g.model_key,
            # style (text -> ResponseStyle),
            style=ResponseStyle(g.style),
            # manual temperature,
            temperature_override=g.temperature_override,
            # reply length.
            max_output_tokens=g.max_output_tokens,
        ),
        # The branding part:
        branding=Branding(
            # title,
            header_title=b.header_title,
            # subtitle,
            header_subtitle=b.header_subtitle,
            # footer,
            footer_text=b.footer_text,
            # greeting,
            greeting=b.greeting,
            # colour,
            primary_color=b.primary_color,
            # launcher side,
            launcher_position=b.launcher_position,
            # logo id.
            logo_asset_id=b.logo_asset_id,
        ),
        retrieval=RetrievalSettings(
            chunk_size_tokens=r.chunk_size_tokens,
            chunk_overlap_ratio=r.chunk_overlap_ratio,
            vector_top_k=r.vector_top_k,
            keyword_top_k=r.keyword_top_k,
            rerank_top_n=r.rerank_top_n,
            faq_threshold=r.faq_threshold,
            confidence_threshold=r.confidence_threshold,
        ),
    )


# Domain version -> API response.
def to_out(v: BotConfigVersion) -> BotConfigVersionOut:
    # Short name for the configuration.
    c = v.config
    # Build and check the response model from a dictionary:
    return BotConfigVersionOut.model_validate(
        # this dictionary:
        {
            # version number,
            "version": v.version,
            # status as text,
            "status": v.status.value,
            # who saved it,
            "created_by": v.created_by,
            # when,
            "created_at": v.created_at,
            # and the configuration:
            "config": {
                # prompt part,
                "prompt": {
                    # persona,
                    "persona": c.prompt.persona,
                    # brand rules,
                    "brand_rules": c.prompt.brand_rules,
                    # custom instructions,
                    "custom_instructions": c.prompt.custom_instructions,
                    # banned topics as a list;
                    "banned_topics": list(c.prompt.banned_topics),
                },
                # generation part,
                "generation": {
                    # model key,
                    "model_key": c.generation.model_key,
                    # style as text,
                    "style": c.generation.style.value,
                    # manual temperature,
                    "temperature_override": c.generation.temperature_override,
                    # reply length;
                    "max_output_tokens": c.generation.max_output_tokens,
                },
                # branding part,
                "branding": {
                    # title,
                    "header_title": c.branding.header_title,
                    # subtitle,
                    "header_subtitle": c.branding.header_subtitle,
                    # footer,
                    "footer_text": c.branding.footer_text,
                    # greeting,
                    "greeting": c.branding.greeting,
                    # colour,
                    "primary_color": c.branding.primary_color,
                    # launcher side,
                    "launcher_position": c.branding.launcher_position,
                    # logo id.
                    "logo_asset_id": c.branding.logo_asset_id,
                },
                "retrieval": {
                    "chunk_size_tokens": c.retrieval.chunk_size_tokens,
                    "chunk_overlap_ratio": c.retrieval.chunk_overlap_ratio,
                    "vector_top_k": c.retrieval.vector_top_k,
                    "keyword_top_k": c.retrieval.keyword_top_k,
                    "rerank_top_n": c.retrieval.rerank_top_n,
                    "faq_threshold": c.retrieval.faq_threshold,
                    "confidence_threshold": c.retrieval.confidence_threshold,
                },
            },
        }
    )


# GET /api/v1/model-options
@options_router.get("/model-options")
# GET the models the caller's plan allows.
async def list_model_options(
    principal: PrincipalDep, service: BotConfigServiceDep
) -> list[ModelOptionOut]:
    # Return each allowed model as {key, label} (no vendor model ids).
    return [
        ModelOptionOut(key=o.key, label=o.label) for o in await service.model_options(principal)
    ]


# Save a new draft.
@router.post("/versions", status_code=status.HTTP_201_CREATED)
# bot_id from the URL; the body is checked as BotConfigIn.
async def save_draft(
    bot_id: UUID, body: BotConfigIn, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    # Body -> domain config, save it as a new draft, return it.
    return to_out(await service.save_draft(principal, bot_id, to_domain(body)))


# Version history.
@router.get("/versions")
# Parameters:
async def list_versions(
    # which bot (from the URL),
    bot_id: UUID,
    # the verified caller,
    principal: PrincipalDep,
    # the ready service,
    service: BotConfigServiceDep,
    # ?limit= (default 20, 1-100).
    limit: int = Query(default=20, ge=1, le=100),
) -> list[BotConfigVersionOut]:
    # Return each version as a response.
    return [to_out(v) for v in await service.list_versions(principal, bot_id, limit)]


# Newest draft.
@router.get("/draft")
# bot_id from the URL.
async def get_draft(
    bot_id: UUID, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    # Return the newest draft (404 if none).
    return to_out(await service.get_draft(principal, bot_id))


# Live version.
@router.get("/published")
# bot_id from the URL.
async def get_published(
    bot_id: UUID, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    # Return the live version (404 if none).
    return to_out(await service.get_published(principal, bot_id))


# Make a version live.
@router.post("/versions/{version}/publish")
# bot_id and the version number from the URL.
async def publish(
    bot_id: UUID, version: int, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    # Publish that version and return it.
    return to_out(await service.publish(principal, bot_id, version))


# Go back to an old version.
@router.post("/versions/{version}/rollback")
# bot_id and the version number from the URL.
async def rollback(
    bot_id: UUID, version: int, principal: PrincipalDep, service: BotConfigServiceDep
) -> BotConfigVersionOut:
    # Re-publish that old version as a new one and return it.
    return to_out(await service.rollback(principal, bot_id, version))


# Logo upload (P4.13): POST /bots/{bot_id}/branding/logo
#   multipart -> platform.security.uploads.validate_logo (PNG/JPEG/WebP, <= 512 KB, no SVG)
#   -> ObjectStore key "t/{tenant_id}/bots/{bot_id}/logo-{uuid}{ext}" -> returns logo_asset_id

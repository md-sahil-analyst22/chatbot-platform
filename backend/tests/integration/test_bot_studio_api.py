# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Bot Studio + widget endpoints: draft -> publish -> widget sees only public
#                fields; invalid branding refused; model options listed.
# How to run: cd backend && uv run pytest tests/integration (no real database: services are
#             swapped for in-memory fakes).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Bot Studio + public widget endpoints with in-memory fakes (no DB)."""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: make_bot = builds a test bot;
#   make_catalog = builds a test catalog.
from tests.fakes.builders import make_bot, make_catalog

# From tests.fakes.in_memory — in-memory stand-ins for the database stores:
#   InMemoryBotConfigRepository = config versions in a dict; InMemoryBotRepository = bots in a
#   dict; InMemoryTenantRepository = tenants in a dict.
from tests.fakes.in_memory import (
    InMemoryBotConfigRepository,
    InMemoryBotRepository,
    InMemoryTenantRepository,
)

# From saathi.api.deps — shared request helpers: the verified caller, a tenant-locked database
#   session: get_principal = verifies the login token.
from saathi.api.deps import get_principal

# From saathi.main — the FastAPI app factory: create_app = builds the FastAPI app.
from saathi.main import create_app

# From saathi.modules.tenancy.api.deps — builds the tenancy services per request: ResolvedWidget
#   = result of resolving a widget key; get_bot_config_service = builds a BotConfigService;
#   get_resolved_widget = resolves a widget key.
from saathi.modules.tenancy.api.deps import (
    ResolvedWidget,
    get_bot_config_service,
    get_resolved_widget,
)

# From saathi.modules.tenancy.application.config_service — the Bot Studio use cases:
#   BotConfigService = the Bot Studio use cases; PublicWidgetConfigService = reads the widget-safe
#   config.
from saathi.modules.tenancy.application.config_service import (
    BotConfigService,
    PublicWidgetConfigService,
)

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; Role = viewer/agent/admin/owner.
from saathi.platform.security.auth import Principal, Role

# The test tenant.
TENANT = UUID("00000000-0000-0000-0000-0000000000cc")
# The only fields /public/v1/widgets/{key}/config may return (R10, 02_ARCHITECTURE_AND_STACK).
PUBLIC_WIDGET_FIELDS = {
    # title,
    "header_title",
    # subtitle,
    "header_subtitle",
    # footer,
    "footer_text",
    # greeting,
    "greeting",
    # colour,
    "primary_color",
    # launcher side,
    "launcher_position",
    # logo address,
    "logo_url",
    # languages.
    "languages",
}
# A valid config body to save:
BODY = {
    # a persona and a banned topic,
    "prompt": {"persona": "Warm receptionist", "banned_topics": ["medical dosage"]},
    # the standard model, precise style,
    "generation": {"model_key": "standard", "style": "precise"},
    # branding:
    "branding": {
        # title,
        "header_title": "ClinicCare",
        # footer,
        "footer_text": "Powered by Saathi",
        # colour.
        "primary_color": "#2563EB",
    },
}


# A fixture: the real app with storage and login swapped for test versions.
@pytest.fixture
# It gives each test (client, bot id, widget key).
async def ctx() -> AsyncIterator[tuple[httpx.AsyncClient, UUID, str]]:
    # Empty in-memory bot and config storage.
    bots, configs = InMemoryBotRepository(), InMemoryBotConfigRepository()
    # A bot in the test tenant...
    bot = make_bot(tenant_id=TENANT)
    # ...saved.
    await bots.add(bot)
    # The Bot Studio service with:
    service = BotConfigService(
        # bot storage,
        bots=bots,
        # config storage,
        configs=configs,
        # a tenant on the growth plan,
        tenants=InMemoryTenantRepository({TENANT: "growth"}),
        # the test catalog.
        catalog=make_catalog(),
    )
    # The real app.
    app = create_app()
    # Skip login: the caller is an admin of the test tenant.
    app.dependency_overrides[get_principal] = lambda: Principal("u1", TENANT, Role.ADMIN)
    # Use our service.
    app.dependency_overrides[get_bot_config_service] = lambda: service
    # Skip the widget-key lookup: every key resolves to our bot.
    app.dependency_overrides[get_resolved_widget] = lambda: ResolvedWidget(
        PublicWidgetConfigService(bots=bots, configs=configs), TENANT, bot.id
    )
    # Run start-up.
    async with app.router.lifespan_context(app):
        # Send requests straight into the app.
        transport = httpx.ASGITransport(app=app)
        # A client.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Lend the client, bot id and widget key to the test.
            yield client, bot.id, bot.public_key


# Save -> publish -> the widget sees exactly the public fields.
async def test_draft_publish_then_widget_reads_public_fields(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack the fixture.
    client, bot_id, public_key = ctx
    # Save a draft.
    r = await client.post(f"/api/v1/bots/{bot_id}/config/versions", json=BODY)
    # 201, as a draft.
    assert r.status_code == 201 and r.json()["status"] == "draft"
    # Publish version 1.
    r = await client.post(f"/api/v1/bots/{bot_id}/config/versions/1/publish")
    # Now published.
    assert r.json()["status"] == "published"

    # Read the public widget config (no login).
    r = await client.get(f"/public/v1/widgets/{public_key}/config")
    # 200.
    assert r.status_code == 200
    # Cacheable for 60 seconds.
    assert r.headers["cache-control"] == "public, max-age=60"
    # The body.
    body = r.json()
    # Shows the published title.
    assert body["header_title"] == "ClinicCare"
    # R10 + 02_ARCHITECTURE_AND_STACK: exactly the public look - no prompts, model, plan or ids.
    assert set(body) == PUBLIC_WIDGET_FIELDS


# Invalid branding is refused.
async def test_invalid_branding_is_rejected(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack.
    client, bot_id, _ = ctx
    # The same body with a dangerous 'colour'.
    bad = {**BODY, "branding": {**BODY["branding"], "primary_color": "javascript:1"}}
    # Try to save it.
    r = await client.post(f"/api/v1/bots/{bot_id}/config/versions", json=bad)
    # 422.
    assert r.status_code == 422


# The model list is filtered by plan.
async def test_model_options_listed(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack.
    client, _, _ = ctx
    # GET the options.
    r = await client.get("/api/v1/model-options")
    # Only 'standard' ('advanced' is pro-only in the test catalog).
    assert [o["key"] for o in r.json()] == ["standard"]

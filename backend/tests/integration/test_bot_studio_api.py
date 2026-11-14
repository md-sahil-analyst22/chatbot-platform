"""Bot Studio + public widget endpoints with in-memory fakes (no DB)."""

from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import pytest
from tests.fakes.builders import make_bot, make_catalog
from tests.fakes.in_memory import (
    InMemoryBotConfigRepository,
    InMemoryBotRepository,
    InMemoryTenantRepository,
)

from saathi.api.deps import get_principal
from saathi.main import create_app
from saathi.modules.tenancy.api.deps import (
    ResolvedWidget,
    get_bot_config_service,
    get_resolved_widget,
)
from saathi.modules.tenancy.application.config_service import (
    BotConfigService,
    PublicWidgetConfigService,
)
from saathi.platform.security.auth import Principal, Role

TENANT = UUID("00000000-0000-0000-0000-0000000000cc")
BODY = {
    "prompt": {"persona": "Warm receptionist", "banned_topics": ["medical dosage"]},
    "generation": {"model_key": "standard", "style": "precise"},
    "branding": {
        "header_title": "ClinicCare",
        "footer_text": "Powered by Saathi",
        "primary_color": "#2563EB",
    },
}


@pytest.fixture
async def ctx() -> AsyncIterator[tuple[httpx.AsyncClient, UUID, str]]:
    bots, configs = InMemoryBotRepository(), InMemoryBotConfigRepository()
    bot = make_bot(tenant_id=TENANT)
    await bots.add(bot)
    service = BotConfigService(
        bots=bots,
        configs=configs,
        tenants=InMemoryTenantRepository({TENANT: "growth"}),
        catalog=make_catalog(),
    )
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: Principal("u1", TENANT, Role.ADMIN)
    app.dependency_overrides[get_bot_config_service] = lambda: service
    app.dependency_overrides[get_resolved_widget] = lambda: ResolvedWidget(
        PublicWidgetConfigService(bots=bots, configs=configs), TENANT, bot.id
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, bot.id, bot.public_key


async def test_draft_publish_then_widget_reads_public_fields(ctx) -> None:  # type: ignore[no-untyped-def]
    client, bot_id, public_key = ctx
    r = await client.post(f"/api/v1/bots/{bot_id}/config/versions", json=BODY)
    assert r.status_code == 201 and r.json()["status"] == "draft"
    r = await client.post(f"/api/v1/bots/{bot_id}/config/versions/1/publish")
    assert r.json()["status"] == "published"

    r = await client.get(f"/public/v1/widgets/{public_key}/config")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=60"
    body = r.json()
    assert body["header_title"] == "ClinicCare"
    assert "persona" not in body and "prompt" not in body


async def test_invalid_branding_is_rejected(ctx) -> None:  # type: ignore[no-untyped-def]
    client, bot_id, _ = ctx
    bad = {**BODY, "branding": {**BODY["branding"], "primary_color": "javascript:1"}}
    r = await client.post(f"/api/v1/bots/{bot_id}/config/versions", json=bad)
    assert r.status_code == 422


async def test_model_options_listed(ctx) -> None:  # type: ignore[no-untyped-def]
    client, _, _ = ctx
    r = await client.get("/api/v1/model-options")
    assert [o["key"] for o in r.json()] == ["standard"]

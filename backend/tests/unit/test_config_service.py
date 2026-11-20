# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The Bot Studio use cases: save draft, publish, rollback, plan limits, roles.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
from uuid import UUID, uuid4

import pytest
from tests.fakes.builders import NOW, make_bot, make_catalog, make_config
from tests.fakes.in_memory import (
    InMemoryBotConfigRepository,
    InMemoryBotRepository,
    InMemoryTenantRepository,
)

from saathi.modules.tenancy.application.config_service import (
    BotConfigService,
    PublicWidgetConfigService,
)
from saathi.modules.tenancy.domain.bot_config import ConfigStatus
from saathi.platform.errors import AuthorizationError, NotFoundError, ValidationError
from saathi.platform.security.auth import Principal, Role

TENANT = UUID("00000000-0000-0000-0000-0000000000aa")
ADMIN = Principal(user_id="admin", tenant_id=TENANT, role=Role.ADMIN)
VIEWER = Principal(user_id="viewer", tenant_id=TENANT, role=Role.VIEWER)


@pytest.fixture
async def ctx() -> tuple[
    BotConfigService, InMemoryBotConfigRepository, UUID, InMemoryBotRepository
]:
    bots, configs = InMemoryBotRepository(), InMemoryBotConfigRepository()
    bot = make_bot(tenant_id=TENANT)
    await bots.add(bot)
    service = BotConfigService(
        bots=bots,
        configs=configs,
        tenants=InMemoryTenantRepository({TENANT: "starter"}),
        catalog=make_catalog(),
        clock=lambda: NOW,
    )
    return service, configs, bot.id, bots


async def test_each_save_creates_a_new_draft_version(ctx) -> None:  # type: ignore[no-untyped-def]
    service, _, bot_id, _ = ctx
    v1 = await service.save_draft(ADMIN, bot_id, make_config())
    v2 = await service.save_draft(ADMIN, bot_id, make_config(title="New"))
    assert (v1.version, v2.version) == (1, 2)
    assert (await service.get_draft(ADMIN, bot_id)).config.branding.header_title == "New"


async def test_model_must_be_allowed_on_plan(ctx) -> None:  # type: ignore[no-untyped-def]
    service, _, bot_id, _ = ctx
    with pytest.raises(ValidationError, match="plan"):
        await service.save_draft(ADMIN, bot_id, make_config(model_key="advanced"))
    assert [o.key for o in await service.model_options(ADMIN)] == ["standard"]


async def test_viewer_cannot_edit_and_unknown_bot_is_404(ctx) -> None:  # type: ignore[no-untyped-def]
    service, _, bot_id, _ = ctx
    with pytest.raises(AuthorizationError):
        await service.save_draft(VIEWER, bot_id, make_config())
    with pytest.raises(NotFoundError):
        await service.save_draft(ADMIN, uuid4(), make_config())


async def test_publish_archives_previous_and_rollback_adds_a_version(ctx) -> None:  # type: ignore[no-untyped-def]
    service, configs, bot_id, _ = ctx
    await service.save_draft(ADMIN, bot_id, make_config(title="One"))
    first = await service.publish(ADMIN, bot_id)
    await service.save_draft(ADMIN, bot_id, make_config(title="Two"))
    second = await service.publish(ADMIN, bot_id)
    assert (await configs.get(TENANT, bot_id, first.version)).status is ConfigStatus.ARCHIVED  # type: ignore[union-attr]
    assert second.status is ConfigStatus.PUBLISHED

    restored = await service.rollback(ADMIN, bot_id, first.version)
    assert restored.version == 3
    assert restored.config.branding.header_title == "One"
    assert (await service.get_published(ADMIN, bot_id)).version == 3


async def test_publish_without_draft_is_404(ctx) -> None:  # type: ignore[no-untyped-def]
    service, _, bot_id, _ = ctx
    with pytest.raises(NotFoundError):
        await service.publish(ADMIN, bot_id)


async def test_public_widget_config_exposes_only_public_fields(ctx) -> None:  # type: ignore[no-untyped-def]
    service, configs, bot_id, bots = ctx
    await service.save_draft(ADMIN, bot_id, make_config(title="TaxMitra"))
    await service.publish(ADMIN, bot_id)
    public = await PublicWidgetConfigService(bots=bots, configs=configs).get(TENANT, bot_id)
    assert public.header_title == "TaxMitra"
    assert not hasattr(public, "custom_instructions")
    with pytest.raises(NotFoundError):
        await PublicWidgetConfigService(bots=bots, configs=configs).get(uuid4(), bot_id)

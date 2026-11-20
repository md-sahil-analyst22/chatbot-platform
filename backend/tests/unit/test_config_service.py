# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The Bot Studio use cases: save draft, publish, rollback, plan limits, roles.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: NOW = a fixed time for tests;
#   make_bot = builds a test bot; make_catalog = builds a test catalog; make_config = builds a
#   test config.
from tests.fakes.builders import NOW, make_bot, make_catalog, make_config

# From tests.fakes.in_memory — in-memory stand-ins for the database stores:
#   InMemoryBotConfigRepository = config versions in a dict; InMemoryBotRepository = bots in a
#   dict; InMemoryTenantRepository = tenants in a dict.
from tests.fakes.in_memory import (
    InMemoryBotConfigRepository,
    InMemoryBotRepository,
    InMemoryTenantRepository,
)

# From saathi.modules.tenancy.application.config_service — the Bot Studio use cases:
#   BotConfigService = the Bot Studio use cases; PublicWidgetConfigService = reads the widget-safe
#   config.
from saathi.modules.tenancy.application.config_service import (
    BotConfigService,
    PublicWidgetConfigService,
)

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   ConfigStatus = draft/published/archived.
from saathi.modules.tenancy.domain.bot_config import ConfigStatus

# From saathi.platform.errors — our error types: AuthorizationError = 403 role not allowed;
#   NotFoundError = 404 not found; ValidationError = 422 invalid input.
from saathi.platform.errors import AuthorizationError, NotFoundError, ValidationError

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; Role = viewer/agent/admin/owner.
from saathi.platform.security.auth import Principal, Role

# A fixed test tenant id.
TENANT = UUID("00000000-0000-0000-0000-0000000000aa")
# A test caller who is an admin of that tenant.
ADMIN = Principal(user_id="admin", tenant_id=TENANT, role=Role.ADMIN)
# A test caller who is only a viewer.
VIEWER = Principal(user_id="viewer", tenant_id=TENANT, role=Role.VIEWER)


# A fixture: pytest builds this fresh for every test that asks for `ctx`.
@pytest.fixture
# It returns (service, config storage, bot id, bot storage).
async def ctx() -> tuple[
    BotConfigService, InMemoryBotConfigRepository, UUID, InMemoryBotRepository
]:
    # Empty in-memory bot and config storage.
    bots, configs = InMemoryBotRepository(), InMemoryBotConfigRepository()
    # A bot in the test tenant...
    bot = make_bot(tenant_id=TENANT)
    # ...saved in the bot storage.
    await bots.add(bot)
    # The service under test, built with:
    service = BotConfigService(
        # the bot storage,
        bots=bots,
        # the config storage,
        configs=configs,
        # a tenant on the 'starter' plan,
        tenants=InMemoryTenantRepository({TENANT: "starter"}),
        # the two-model test catalog,
        catalog=make_catalog(),
        # a clock frozen at NOW.
        clock=lambda: NOW,
    )
    # Hand everything to the test.
    return service, configs, bot.id, bots


# Every save creates a new version number.
async def test_each_save_creates_a_new_draft_version(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack the fixture: service, config storage, bot id, bot storage ('_' = not needed
    #   here).
    service, _, bot_id, _ = ctx
    # Save a draft -> version 1.
    v1 = await service.save_draft(ADMIN, bot_id, make_config())
    # Save another -> version 2.
    v2 = await service.save_draft(ADMIN, bot_id, make_config(title="New"))
    # Numbers are 1 and 2.
    assert (v1.version, v2.version) == (1, 2)
    # The newest draft is the second one.
    assert (await service.get_draft(ADMIN, bot_id)).config.branding.header_title == "New"


# A model outside the plan is refused.
async def test_model_must_be_allowed_on_plan(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack the fixture: service, config storage, bot id, bot storage ('_' = not needed
    #   here).
    service, _, bot_id, _ = ctx
    # Expect a ValidationError mentioning 'plan'...
    with pytest.raises(ValidationError, match="plan"):
        # ...when a starter tenant picks 'advanced'.
        await service.save_draft(ADMIN, bot_id, make_config(model_key="advanced"))
    # And starter only sees 'standard'.
    assert [o.key for o in await service.model_options(ADMIN)] == ["standard"]


# Viewers can't save; unknown bots give 404.
async def test_viewer_cannot_edit_and_unknown_bot_is_404(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack the fixture: service, config storage, bot id, bot storage ('_' = not needed
    #   here).
    service, _, bot_id, _ = ctx
    # Expect 403...
    with pytest.raises(AuthorizationError):
        # ...when a viewer saves.
        await service.save_draft(VIEWER, bot_id, make_config())
    # Expect 404...
    with pytest.raises(NotFoundError):
        # ...for a bot id that doesn't exist.
        await service.save_draft(ADMIN, uuid4(), make_config())


# Publishing archives the old live version; rollback creates a new version.
async def test_publish_archives_previous_and_rollback_adds_a_version(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack the fixture: service, config storage, bot id, bot storage ('_' = not needed
    #   here).
    service, configs, bot_id, _ = ctx
    # Save draft 'One'...
    await service.save_draft(ADMIN, bot_id, make_config(title="One"))
    # ...and publish it (version 1).
    first = await service.publish(ADMIN, bot_id)
    # Save draft 'Two'...
    await service.save_draft(ADMIN, bot_id, make_config(title="Two"))
    # ...and publish it (version 2).
    second = await service.publish(ADMIN, bot_id)
    # Version 1 is now archived.
    assert (await configs.get(TENANT, bot_id, first.version)).status is ConfigStatus.ARCHIVED  # type: ignore[union-attr]
    # Version 2 is live.
    assert second.status is ConfigStatus.PUBLISHED

    # Roll back to version 1.
    restored = await service.rollback(ADMIN, bot_id, first.version)
    # That creates version 3...
    assert restored.version == 3
    # ...with version 1's content...
    assert restored.config.branding.header_title == "One"
    # ...and version 3 is now live.
    assert (await service.get_published(ADMIN, bot_id)).version == 3


# Publishing with no draft gives 404.
async def test_publish_without_draft_is_404(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack the fixture: service, config storage, bot id, bot storage ('_' = not needed
    #   here).
    service, _, bot_id, _ = ctx
    # Expect 404...
    with pytest.raises(NotFoundError):
        # ...because nothing was saved.
        await service.publish(ADMIN, bot_id)


# The widget sees only public fields, and only for the right tenant.
async def test_public_widget_config_exposes_only_public_fields(ctx) -> None:  # type: ignore[no-untyped-def]
    # Unpack the fixture: service, config storage, bot id, bot storage ('_' = not needed
    #   here).
    service, configs, bot_id, bots = ctx
    # Save a draft titled 'TaxMitra'...
    await service.save_draft(ADMIN, bot_id, make_config(title="TaxMitra"))
    # ...and publish it.
    await service.publish(ADMIN, bot_id)
    # Read the widget config.
    public = await PublicWidgetConfigService(bots=bots, configs=configs).get(TENANT, bot_id)
    # The title is there.
    assert public.header_title == "TaxMitra"
    # Private fields (instructions) are not.
    assert not hasattr(public, "custom_instructions")
    # Expect 404...
    with pytest.raises(NotFoundError):
        # ...when another tenant asks for this bot.
        await PublicWidgetConfigService(bots=bots, configs=configs).get(uuid4(), bot_id)

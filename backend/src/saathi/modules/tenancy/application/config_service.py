# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The Bot Studio use cases: save a draft, publish it, roll back, read versions, list
#       allowed models.
# Plus: PublicWidgetConfigService: the small, safe piece of config the public widget may read.
# Safety: 🔒 Only admins/owners change configs; the chosen model must be on the tenant's plan.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Bot Studio use cases: save draft, publish, roll back, read versions, list allowed models."""

# From collections.abc — standard type names for collections: Callable = type for a function.
from collections.abc import Callable

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From datetime — dates and times: UTC = the UTC time zone; datetime = a date + time value.
from datetime import UTC, datetime

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfig = one full configuration; BotConfigVersion = one saved version; ConfigStatus =
#   draft/published/archived.
from saathi.modules.tenancy.domain.bot_config import BotConfig, BotConfigVersion, ConfigStatus

# From saathi.modules.tenancy.ports.repositories — tenancy storage contracts:
#   BotConfigRepository = contract: store config versions; BotRepository = contract: store bots;
#   TenantRepository = contract: tenant facts.
from saathi.modules.tenancy.ports.repositories import (
    BotConfigRepository,
    BotRepository,
    TenantRepository,
)

# From saathi.platform.config.model_catalog — the list of AI models tenants may choose:
#   ModelCatalog = the catalog; ModelOption = one choosable model.
from saathi.platform.config.model_catalog import ModelCatalog, ModelOption

# From saathi.platform.errors — our error types: NotFoundError = 404 not found; ValidationError
#   = 422 invalid input.
from saathi.platform.errors import NotFoundError, ValidationError

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; Role = viewer/agent/admin/owner; require_role = stops with 403 if the role is
#   too low.
from saathi.platform.security.auth import Principal, Role, require_role

Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Bot Studio use cases. `clock` can be replaced in tests to control time.
class BotConfigService:
    def __init__(
        self,
        *,
        bots: BotRepository,
        configs: BotConfigRepository,
        tenants: TenantRepository,
        catalog: ModelCatalog,
        clock: Clock = _utcnow,
    ) -> None:
        self._bots = bots
        self._configs = configs
        self._tenants = tenants
        self._catalog = catalog
        self._clock = clock

    # 404 if the bot doesn't exist in the caller's workspace.
    async def _require_bot(self, principal: Principal, bot_id: UUID) -> None:
        if await self._bots.get(principal.tenant_id, bot_id) is None:
            raise NotFoundError("bot not found")

    # The caller's plan (default 'starter').
    async def _plan(self, principal: Principal) -> str:
        return await self._tenants.get_plan(principal.tenant_id) or "starter"

    # The models the caller's plan allows.
    async def model_options(self, principal: Principal) -> list[ModelOption]:
        require_role(principal, Role.VIEWER)
        return self._catalog.options_for_plan(await self._plan(principal))

    # Save a new draft version (always a new number - old versions are never overwritten).
    async def save_draft(
        self, principal: Principal, bot_id: UUID, config: BotConfig
    ) -> BotConfigVersion:
        require_role(principal, Role.ADMIN)
        await self._require_bot(principal, bot_id)
        if not self._catalog.is_allowed(config.generation.model_key, await self._plan(principal)):
            raise ValidationError("this model is not available on your plan")
        version = BotConfigVersion(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            bot_id=bot_id,
            version=await self._configs.next_version(principal.tenant_id, bot_id),
            status=ConfigStatus.DRAFT,
            config=config,
            created_by=principal.user_id,
            created_at=self._clock(),
        )
        await self._configs.add(version)
        return version

    # Make a version live.
    async def publish(
        self, principal: Principal, bot_id: UUID, version: int | None = None
    ) -> BotConfigVersion:
        """Archive the live version and publish the target, in the caller's single transaction."""
        require_role(principal, Role.ADMIN)
        await self._require_bot(principal, bot_id)
        target = (
            await self._configs.get(principal.tenant_id, bot_id, version)
            if version is not None
            else await self._configs.latest_draft(principal.tenant_id, bot_id)
        )
        if target is None:
            raise NotFoundError("draft version not found")
        # Archive the currently live version first, so only one is ever published.
        current = await self._configs.published(principal.tenant_id, bot_id)
        if current is not None:
            await self._configs.update_status(current.archived())
        live = target.published()
        await self._configs.update_status(live)
        return live

    # Go back to an old version by copying it into a new draft and publishing that.
    async def rollback(self, principal: Principal, bot_id: UUID, version: int) -> BotConfigVersion:
        """Re-publish an old configuration as a NEW version (history stays intact)."""
        require_role(principal, Role.ADMIN)
        old = await self._configs.get(principal.tenant_id, bot_id, version)
        if old is None:
            raise NotFoundError("version not found")
        draft = await self.save_draft(principal, bot_id, old.config)
        return await self.publish(principal, bot_id, draft.version)

    # The newest draft.
    async def get_draft(self, principal: Principal, bot_id: UUID) -> BotConfigVersion:
        require_role(principal, Role.VIEWER)
        draft = await self._configs.latest_draft(principal.tenant_id, bot_id)
        if draft is None:
            raise NotFoundError("no draft yet")
        return draft

    # The live version.
    async def get_published(self, principal: Principal, bot_id: UUID) -> BotConfigVersion:
        require_role(principal, Role.VIEWER)
        live = await self._configs.published(principal.tenant_id, bot_id)
        if live is None:
            raise NotFoundError("bot has no published configuration")
        return live

    # Version history, newest first (max 100).
    async def list_versions(
        self, principal: Principal, bot_id: UUID, limit: int = 20
    ) -> list[BotConfigVersion]:
        require_role(principal, Role.VIEWER)
        return await self._configs.list_versions(principal.tenant_id, bot_id, min(limit, 100))


@dataclass(frozen=True, slots=True)
# 🔒 Only widget-safe fields (no prompt, no model, no plan).
class PublicWidgetConfig:
    """Only fields that are safe for anyone on the internet to read."""

    bot_id: UUID
    header_title: str
    header_subtitle: str
    footer_text: str
    greeting: str
    primary_color: str
    launcher_position: str
    logo_asset_id: UUID | None
    languages: tuple[str, ...]


# Reads the live config for the public widget.
class PublicWidgetConfigService:
    def __init__(self, *, bots: BotRepository, configs: BotConfigRepository) -> None:
        self._bots = bots
        self._configs = configs

    async def get(self, tenant_id: UUID, bot_id: UUID) -> PublicWidgetConfig:
        bot = await self._bots.get(tenant_id, bot_id)
        live = await self._configs.published(tenant_id, bot_id)
        if bot is None or live is None:
            raise NotFoundError("widget not found")
        b = live.config.branding
        return PublicWidgetConfig(
            bot_id=bot.id,
            header_title=b.header_title,
            header_subtitle=b.header_subtitle,
            footer_text=b.footer_text,
            greeting=b.greeting,
            primary_color=b.primary_color,
            launcher_position=b.launcher_position,
            logo_asset_id=b.logo_asset_id,
            languages=bot.languages,
        )

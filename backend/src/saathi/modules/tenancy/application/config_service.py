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

# Type name: a clock is a function that returns the current time.
Clock = Callable[[], datetime]


# The real clock...
def _utcnow() -> datetime:
    # ...returns the current time in UTC.
    return datetime.now(UTC)


# Bot Studio use cases. `clock` can be replaced in tests to control time.
class BotConfigService:
    # Everything the service needs is handed in:
    def __init__(
        self,
        *,
        bots: BotRepository,
        # config version storage,
        configs: BotConfigRepository,
        # tenant facts,
        tenants: TenantRepository,
        # the model catalog,
        catalog: ModelCatalog,
        # and a clock (tests pass a fixed one).
        clock: Clock = _utcnow,
    ) -> None:
        # Remember the bot storage.
        self._bots = bots
        # Remember the config storage.
        self._configs = configs
        # Remember the tenant facts.
        self._tenants = tenants
        # Remember the catalog.
        self._catalog = catalog
        # Remember the clock.
        self._clock = clock

    # 404 if the bot doesn't exist in the caller's workspace.
    async def _require_bot(self, principal: Principal, bot_id: UUID) -> None:
        # The bot isn't in the caller's tenant...
        if await self._bots.get(principal.tenant_id, bot_id) is None:
            # ...so 404.
            raise NotFoundError("bot not found")

    # The caller's plan (default 'starter').
    async def _plan(self, principal: Principal) -> str:
        # The plan from the database, or 'starter' if none is set.
        return await self._tenants.get_plan(principal.tenant_id) or "starter"

    # The models the caller's plan allows.
    async def model_options(self, principal: Principal) -> list[ModelOption]:
        # Any member may see the models.
        require_role(principal, Role.VIEWER)
        # Only the models the caller's plan includes.
        return self._catalog.options_for_plan(await self._plan(principal))

    # Save a new draft version (always a new number - old versions are never overwritten).
    async def save_draft(
        self, principal: Principal, bot_id: UUID, config: BotConfig
    ) -> BotConfigVersion:
        # 🔒 Only admins and owners may save.
        require_role(principal, Role.ADMIN)
        # The bot must exist in the caller's tenant.
        await self._require_bot(principal, bot_id)
        # The chosen model must be on the caller's plan...
        if not self._catalog.is_allowed(config.generation.model_key, await self._plan(principal)):
            # ...otherwise 422.
            raise ValidationError("this model is not available on your plan")
        # Build the new version:
        version = BotConfigVersion(
            # a new random id,
            id=uuid4(),
            # 🔒 the caller's tenant (from the token),
            tenant_id=principal.tenant_id,
            # the bot,
            bot_id=bot_id,
            # the next version number,
            version=await self._configs.next_version(principal.tenant_id, bot_id),
            # status 'draft',
            status=ConfigStatus.DRAFT,
            # the configuration,
            config=config,
            # who saved it,
            created_by=principal.user_id,
            # and when.
            created_at=self._clock(),
        )
        # Save it.
        await self._configs.add(version)
        # Return it.
        return version

    # Make a version live.
    async def publish(
        self, principal: Principal, bot_id: UUID, version: int | None = None
    ) -> BotConfigVersion:
        """Archive the live version and publish the target, in the caller's single transaction."""
        # 🔒 Only admins and owners may publish.
        require_role(principal, Role.ADMIN)
        # The bot must exist in the caller's tenant.
        await self._require_bot(principal, bot_id)
        # Which version to publish: the one asked for, or else the newest draft.
        target = (
            await self._configs.get(principal.tenant_id, bot_id, version)
            if version is not None
            else await self._configs.latest_draft(principal.tenant_id, bot_id)
        )
        # Nothing to publish:
        if target is None:
            # 404.
            raise NotFoundError("draft version not found")
        # Archive the currently live version first, so only one is ever published.
        current = await self._configs.published(principal.tenant_id, bot_id)
        # If something is live now...
        if current is not None:
            # ...mark it archived.
            await self._configs.update_status(current.archived())
        # Make a 'published' copy of the target (only drafts are allowed).
        live = target.published()
        # Save that status change.
        await self._configs.update_status(live)
        # Return the live version.
        return live

    # Go back to an old version by copying it into a new draft and publishing that.
    async def rollback(self, principal: Principal, bot_id: UUID, version: int) -> BotConfigVersion:
        """Re-publish an old configuration as a NEW version (history stays intact)."""
        # 🔒 Only admins and owners may roll back.
        require_role(principal, Role.ADMIN)
        # Find the old version.
        old = await self._configs.get(principal.tenant_id, bot_id, version)
        # It doesn't exist:
        if old is None:
            # 404.
            raise NotFoundError("version not found")
        # Save its configuration as a brand-new draft...
        draft = await self.save_draft(principal, bot_id, old.config)
        # ...and publish that draft.
        return await self.publish(principal, bot_id, draft.version)

    # The newest draft.
    async def get_draft(self, principal: Principal, bot_id: UUID) -> BotConfigVersion:
        # Any member may read the draft.
        require_role(principal, Role.VIEWER)
        # The newest draft.
        draft = await self._configs.latest_draft(principal.tenant_id, bot_id)
        # None yet:
        if draft is None:
            # 404.
            raise NotFoundError("no draft yet")
        # Return it.
        return draft

    # The live version.
    async def get_published(self, principal: Principal, bot_id: UUID) -> BotConfigVersion:
        # Any member may read the live version.
        require_role(principal, Role.VIEWER)
        # The live version.
        live = await self._configs.published(principal.tenant_id, bot_id)
        # Nothing published yet:
        if live is None:
            # 404.
            raise NotFoundError("bot has no published configuration")
        # Return it.
        return live

    # Version history, newest first (max 100).
    async def list_versions(
        self, principal: Principal, bot_id: UUID, limit: int = 20
    ) -> list[BotConfigVersion]:
        # Any member may see the history.
        require_role(principal, Role.VIEWER)
        # The history, never more than 100 versions.
        return await self._configs.list_versions(principal.tenant_id, bot_id, min(limit, 100))


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# 🔒 Only widget-safe fields (no prompt, no model, no plan).
class PublicWidgetConfig:
    """Only fields that are safe for anyone on the internet to read."""

    # Which bot.
    bot_id: UUID
    # Chat window title.
    header_title: str
    # Subtitle.
    header_subtitle: str
    # Footer.
    footer_text: str
    # First message.
    greeting: str
    # Main colour.
    primary_color: str
    # Launcher side.
    launcher_position: str
    # Logo, if any.
    logo_asset_id: UUID | None
    # Languages the bot speaks.
    languages: tuple[str, ...]


# Reads the live config for the public widget.
class PublicWidgetConfigService:
    # Only the storage it needs: bots and config versions.
    def __init__(self, *, bots: BotRepository, configs: BotConfigRepository) -> None:
        # Remember the bot storage.
        self._bots = bots
        # Remember the config storage.
        self._configs = configs

    # Called after the widget key was resolved to (tenant, bot).
    async def get(self, tenant_id: UUID, bot_id: UUID) -> PublicWidgetConfig:
        # The bot.
        bot = await self._bots.get(tenant_id, bot_id)
        # Its live version.
        live = await self._configs.published(tenant_id, bot_id)
        # No bot or nothing published...
        if bot is None or live is None:
            # ...means 404 (the widget shows nothing).
            raise NotFoundError("widget not found")
        # Short name for the branding part.
        b = live.config.branding
        # Copy ONLY the safe display fields:
        return PublicWidgetConfig(
            # bot id,
            bot_id=bot.id,
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
            # logo,
            logo_asset_id=b.logo_asset_id,
            # languages.
            languages=bot.languages,
        )

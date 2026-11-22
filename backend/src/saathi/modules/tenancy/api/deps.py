# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Builds the tenancy services for each request, plugging the database code into them.
# Why: Routes ask FastAPI for a ready service; tests swap these functions for fakes.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Module-level wiring for the HTTP layer: builds use-case services from their adapters.

Routes depend on services only. Tests override these functions with in-memory fakes.
"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`; Callable = a function type.
from collections.abc import AsyncIterator, Callable

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From typing — type-hint helpers: Annotated = a type plus extra info (e.g. a FastAPI
#   dependency).
from typing import Annotated

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From fastapi — the web framework that turns Python functions into web endpoints: Depends =
#   asks FastAPI to hand over a ready-made object (dependency injection); Path = rules for a value
#   in the URL path; Request = the incoming request (gives access to app.state).
from fastapi import Depends, Path, Request

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncSession =
#   one unit of database work; async_sessionmaker = factory that creates sessions.
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# From saathi.api.deps — shared request helpers: the verified caller, a tenant-locked database
#   session: AfterCommitDep = the request's after-commit list; TenantDbDep = a database session
#   locked to the caller's tenant; get_model_catalog =
#   the shared model catalog; get_sessionmaker = the shared database session factory.
from saathi.api.deps import AfterCommitDep, TenantDbDep, get_model_catalog, get_sessionmaker

# From saathi.modules.tenancy.adapters.config_repository — database code for config versions:
#   SqlAlchemyBotConfigRepository = config versions in the database.
from saathi.modules.tenancy.adapters.config_repository import SqlAlchemyBotConfigRepository

# From saathi.modules.tenancy.adapters.public_lookup — widget key -> tenant lookup:
#   SqlAlchemyPublicBotLookup = finds the tenant for a widget key.
from saathi.modules.tenancy.adapters.public_lookup import SqlAlchemyPublicBotLookup

# From saathi.modules.tenancy.adapters.repository — database code for bots and tenants:
#   SqlAlchemyBotRepository = bots in the database; SqlAlchemyTenantRepository = tenant facts in
#   the database.
from saathi.modules.tenancy.adapters.repository import (
    SqlAlchemyBotRepository,
    SqlAlchemyTenantRepository,
)

# From saathi.modules.tenancy.api.schemas — the JSON shapes of the tenancy API: PUBLIC_KEY_REGEX
#   = allowed widget-key format.
from saathi.modules.tenancy.api.schemas import PUBLIC_KEY_REGEX

# From saathi.modules.tenancy.application.config_service — the Bot Studio use cases:
#   BotConfigService = the Bot Studio use cases; PublicWidgetConfigService = reads the widget-safe
#   config.
from saathi.modules.tenancy.application.config_service import (
    BotConfigService,
    PublicWidgetConfigService,
)

# From saathi.modules.tenancy.application.services — the bot use cases: BotService = the bot use
#   cases.
from saathi.modules.tenancy.application.services import BotService

# From saathi.modules.tenancy.ports.hooks — publish reaction contract: ConfigPublishedHook.
from saathi.modules.tenancy.ports.hooks import ConfigPublishedHook

# From saathi.platform.config.model_catalog — the list of AI models tenants may choose:
#   ModelCatalog = the catalog.
from saathi.platform.config.model_catalog import ModelCatalog

# From saathi.platform.db.after_commit — after-commit hooks: AfterCommit = work run after COMMIT.
from saathi.platform.db.after_commit import AfterCommit

# From saathi.platform.db.tenant_context — locks a database session to one tenant:
#   tenant_session = a session locked to one tenant.
from saathi.platform.db.tenant_context import tenant_session

# From saathi.platform.errors — our error types: NotFoundError = 404 not found.
from saathi.platform.errors import NotFoundError

# app.state.config_publish_hook: builds the publish reaction on the request's session and
#   after-commit list (wired in bootstrap/, backed by the knowledge module).
PublishHookFactory = Callable[[AsyncSession, AfterCommit], ConfigPublishedHook]


# A BotService using a tenant-locked database session.
async def get_bot_service(db: TenantDbDep) -> BotService:
    # A BotService that stores bots in this tenant-locked session.
    return BotService(SqlAlchemyBotRepository(db))


# A BotConfigService with all its repositories and the model catalog.
async def get_bot_config_service(
    request: Request,
    db: TenantDbDep,
    after_commit: AfterCommitDep,
    catalog: Annotated[ModelCatalog, Depends(get_model_catalog)],
) -> BotConfigService:
    # The publish reaction (re-process documents when chunking settings change).
    hook_factory: PublishHookFactory = request.app.state.config_publish_hook
    # Build the service with:
    return BotConfigService(
        # bot storage,
        bots=SqlAlchemyBotRepository(db),
        # config-version storage,
        configs=SqlAlchemyBotConfigRepository(db),
        # tenant facts,
        tenants=SqlAlchemyTenantRepository(db),
        # the catalog (all sharing the same session/transaction),
        catalog=catalog,
        # and the publish reaction, on the same session (its jobs are sent after commit).
        publish_hook=hook_factory(db, after_commit),
    )


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# The result of resolving a public widget key.
class ResolvedWidget:
    # The ready service for reading the widget config.
    service: PublicWidgetConfigService
    # The tenant the key belongs to.
    tenant_id: UUID
    # The bot the key belongs to.
    bot_id: UUID


# For anonymous widget requests.
async def get_resolved_widget(
    # The key from the URL; it must match the pk_... format (else 422).
    public_key: Annotated[str, Path(pattern=PUBLIC_KEY_REGEX)],
    # FastAPI supplies the session factory.
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> AsyncIterator[ResolvedWidget]:
    """Anonymous widget request: resolve key -> tenant, then read inside that tenant's RLS scope."""
    # Step 1: key -> tenant (no tenant context yet; narrow lookup only).
    async with sessionmaker() as session:
        # Look the key up with the narrow database function.
        ref = await SqlAlchemyPublicBotLookup(session).resolve(public_key)
    # Unknown key:
    if ref is None:
        # 404.
        raise NotFoundError("widget not found")
    # 🔒 Step 2: read the config inside THAT tenant's row-level security.
    async with tenant_session(sessionmaker, ref.tenant_id) as session:
        # Lend the result to the endpoint:
        yield ResolvedWidget(
            # a service whose storage uses this tenant-locked session,
            service=PublicWidgetConfigService(
                # bot storage,
                bots=SqlAlchemyBotRepository(session),
                # config storage,
                configs=SqlAlchemyBotConfigRepository(session),
            ),
            # the tenant,
            tenant_id=ref.tenant_id,
            # the bot.
            bot_id=ref.bot_id,
        )


# Short names routes use to ask for these services.
BotServiceDep = Annotated[BotService, Depends(get_bot_service)]
# Endpoints write `service: BotConfigServiceDep` to get a ready BotConfigService.
BotConfigServiceDep = Annotated[BotConfigService, Depends(get_bot_config_service)]
# Endpoints write `widget: ResolvedWidgetDep` to get a resolved widget.
ResolvedWidgetDep = Annotated[ResolvedWidget, Depends(get_resolved_widget)]

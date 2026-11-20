# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Builds the tenancy services for each request, plugging the database code into them.
# Why: Routes ask FastAPI for a ready service; tests swap these functions for fakes.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Module-level wiring for the HTTP layer: builds use-case services from their adapters.

Routes depend on services only. Tests override these functions with in-memory fakes.
"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

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
#   in the URL path.
from fastapi import Depends, Path

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncSession =
#   one unit of database work; async_sessionmaker = factory that creates sessions.
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# From saathi.api.deps — shared request helpers: the verified caller, a tenant-locked database
#   session: TenantDbDep = a database session locked to the caller's tenant; get_model_catalog =
#   the shared model catalog; get_sessionmaker = the shared database session factory.
from saathi.api.deps import TenantDbDep, get_model_catalog, get_sessionmaker

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

# From saathi.platform.config.model_catalog — the list of AI models tenants may choose:
#   ModelCatalog = the catalog.
from saathi.platform.config.model_catalog import ModelCatalog

# From saathi.platform.db.tenant_context — locks a database session to one tenant:
#   tenant_session = a session locked to one tenant.
from saathi.platform.db.tenant_context import tenant_session

# From saathi.platform.errors — our error types: NotFoundError = 404 not found.
from saathi.platform.errors import NotFoundError


# A BotService using a tenant-locked database session.
async def get_bot_service(db: TenantDbDep) -> BotService:
    return BotService(SqlAlchemyBotRepository(db))


# A BotConfigService with all its repositories and the model catalog.
async def get_bot_config_service(
    db: TenantDbDep, catalog: Annotated[ModelCatalog, Depends(get_model_catalog)]
) -> BotConfigService:
    return BotConfigService(
        bots=SqlAlchemyBotRepository(db),
        configs=SqlAlchemyBotConfigRepository(db),
        tenants=SqlAlchemyTenantRepository(db),
        catalog=catalog,
    )


@dataclass(frozen=True, slots=True)
# The result of resolving a public widget key.
class ResolvedWidget:
    service: PublicWidgetConfigService
    tenant_id: UUID
    bot_id: UUID


# For anonymous widget requests.
async def get_resolved_widget(
    public_key: Annotated[str, Path(pattern=PUBLIC_KEY_REGEX)],
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
) -> AsyncIterator[ResolvedWidget]:
    """Anonymous widget request: resolve key -> tenant, then read inside that tenant's RLS scope."""
    # Step 1: key -> tenant (no tenant context yet; narrow lookup only).
    async with sessionmaker() as session:
        ref = await SqlAlchemyPublicBotLookup(session).resolve(public_key)
    if ref is None:
        raise NotFoundError("widget not found")
    # 🔒 Step 2: read the config inside THAT tenant's row-level security.
    async with tenant_session(sessionmaker, ref.tenant_id) as session:
        yield ResolvedWidget(
            service=PublicWidgetConfigService(
                bots=SqlAlchemyBotRepository(session),
                configs=SqlAlchemyBotConfigRepository(session),
            ),
            tenant_id=ref.tenant_id,
            bot_id=ref.bot_id,
        )


# Short names routes use to ask for these services.
BotServiceDep = Annotated[BotService, Depends(get_bot_service)]
BotConfigServiceDep = Annotated[BotConfigService, Depends(get_bot_config_service)]
ResolvedWidgetDep = Annotated[ResolvedWidget, Depends(get_resolved_widget)]

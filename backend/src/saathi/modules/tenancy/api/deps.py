# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Builds the tenancy services for each request, plugging the database code into them.
# Why: Routes ask FastAPI for a ready service; tests swap these functions for fakes.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Module-level wiring for the HTTP layer: builds use-case services from their adapters.

Routes depend on services only. Tests override these functions with in-memory fakes.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saathi.api.deps import TenantDbDep, get_model_catalog, get_sessionmaker
from saathi.modules.tenancy.adapters.config_repository import SqlAlchemyBotConfigRepository
from saathi.modules.tenancy.adapters.public_lookup import SqlAlchemyPublicBotLookup
from saathi.modules.tenancy.adapters.repository import (
    SqlAlchemyBotRepository,
    SqlAlchemyTenantRepository,
)
from saathi.modules.tenancy.api.schemas import PUBLIC_KEY_REGEX
from saathi.modules.tenancy.application.config_service import (
    BotConfigService,
    PublicWidgetConfigService,
)
from saathi.modules.tenancy.application.services import BotService
from saathi.platform.config.model_catalog import ModelCatalog
from saathi.platform.db.tenant_context import tenant_session
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

"""Process-wide resources, built once (FastAPI lifespan / worker startup) and closed once.

The container owns lifecycles. Consumers never receive the whole container: api/deps.py
exposes one narrow dependency per resource (Interface Segregation).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from saathi.bootstrap import providers  # noqa: F401  (registers all adapters)
from saathi.platform.config.model_catalog import ModelCatalog, default_catalog
from saathi.platform.config.settings import Settings
from saathi.platform.db.engine import build_engine, build_sessionmaker
from saathi.platform.http import build_http_client
from saathi.platform.security.auth import TokenVerifier


@dataclass(slots=True)
class Container:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    http: httpx.AsyncClient
    model_catalog: ModelCatalog
    token_verifier: TokenVerifier | None

    @classmethod
    def build(cls, settings: Settings) -> Container:
        engine = build_engine(settings.database_url.get_secret_value())
        return cls(
            settings=settings,
            engine=engine,
            sessionmaker=build_sessionmaker(engine),
            redis=Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True),
            http=build_http_client(),
            model_catalog=default_catalog(),
            # P1.7: plug in the Supabase/Clerk JWKS verifier. None => 401 everywhere (fail closed).
            token_verifier=None,
        )

    async def aclose(self) -> None:
        await self.http.aclose()
        await self.redis.aclose()
        await self.engine.dispose()

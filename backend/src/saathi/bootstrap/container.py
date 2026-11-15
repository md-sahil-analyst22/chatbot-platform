"""Process-wide resources, built once (FastAPI lifespan / worker startup) and closed once.

The container owns lifecycles. Consumers never receive the whole container: api/deps.py
exposes one narrow dependency per resource (Interface Segregation).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from saathi.bootstrap import providers  # noqa: F401  (registers all adapters)
from saathi.modules.tenancy.adapters.membership_lookup import SqlAlchemyMembershipLookup
from saathi.platform.config.model_catalog import ModelCatalog, default_catalog
from saathi.platform.config.settings import Settings
from saathi.platform.db.engine import build_engine, build_sessionmaker, ping_database
from saathi.platform.errors import ConfigurationError
from saathi.platform.http import build_http_client
from saathi.platform.security.auth import TokenVerifier
from saathi.platform.security.jwt_verifier import JwksTokenVerifier


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
        sessionmaker = build_sessionmaker(engine)
        http = build_http_client()
        return cls(
            settings=settings,
            engine=engine,
            sessionmaker=sessionmaker,
            redis=Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True),
            http=http,
            model_catalog=default_catalog(),
            token_verifier=build_token_verifier(settings, http, sessionmaker),
        )

    def readiness_checks(self) -> Mapping[str, Callable[[], Awaitable[object]]]:
        """Dependencies the API needs before it can serve traffic (used by /ready)."""
        return {"database": self._ping_database, "redis": self._ping_redis}

    async def _ping_database(self) -> None:
        await ping_database(self.engine)

    async def _ping_redis(self) -> None:
        await self.redis.ping()

    async def aclose(self) -> None:
        await self.http.aclose()
        await self.redis.aclose()
        await self.engine.dispose()


def build_token_verifier(
    settings: Settings,
    http: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> TokenVerifier | None:
    """ADR-0007. None means every /api/v1 call is refused (fail closed, R16)."""
    url, issuer, audience = settings.auth_jwks_url, settings.auth_issuer, settings.auth_audience
    if url and issuer and audience:
        return JwksTokenVerifier(
            http,
            jwks_url=url,
            issuer=issuer,
            audience=audience,
            memberships=SqlAlchemyMembershipLookup(sessionmaker),
        )
    if settings.env in ("staging", "production"):
        # A deployed API that can't authenticate anyone is a misconfiguration: refuse to start.
        raise ConfigurationError("AUTH_JWKS_URL, AUTH_ISSUER and AUTH_AUDIENCE must be set")
    return None

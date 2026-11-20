# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The 'toolbox' built once per process: settings, database pool, Redis, HTTP client, model
#       catalog and login checker.
# Why: Creating connections per request would be slow and leak resources. One shared toolbox,
#      closed cleanly at shutdown.
# Used by: main.py (the API's lifespan). Request handlers never see the whole container - only
#          single tools via app.state.
# ─────────────────────────────────────────────────────────────────────────────────────────────
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

# Importing this file registers every vendor adapter (Gemini, Sarvam, Supabase...) in its phone
# book.
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
# The toolbox. `@dataclass` just means 'a class that mainly holds these fields'.
class Container:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    http: httpx.AsyncClient
    model_catalog: ModelCatalog
    token_verifier: TokenVerifier | None

    @classmethod
    # Create every tool from the settings. Nothing connects yet - connections open on first use.
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

    # Which checks /ready runs: can we reach the database and Redis?
    def readiness_checks(self) -> Mapping[str, Callable[[], Awaitable[object]]]:
        """Dependencies the API needs before it can serve traffic (used by /ready)."""
        return {"database": self._ping_database, "redis": self._ping_redis}

    # One tiny `SELECT 1` round trip.
    async def _ping_database(self) -> None:
        await ping_database(self.engine)

    # One Redis PING.
    async def _ping_redis(self) -> None:
        await self.redis.ping()

    # Close everything at shutdown, in reverse order of importance.
    async def aclose(self) -> None:
        await self.http.aclose()
        await self.redis.aclose()
        await self.engine.dispose()


# 🔒 Decide how logins are checked (ADR-0007).
def build_token_verifier(
    settings: Settings,
    http: httpx.AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> TokenVerifier | None:
    """ADR-0007. None means every /api/v1 call is refused (fail closed, R16)."""
    url, issuer, audience = settings.auth_jwks_url, settings.auth_issuer, settings.auth_audience
    # All three login settings present: check Supabase tokens and look up the user's workspace.
    if url and issuer and audience:
        return JwksTokenVerifier(
            http,
            jwks_url=url,
            issuer=issuer,
            audience=audience,
            memberships=SqlAlchemyMembershipLookup(sessionmaker),
        )
    # 🔒 A live server that can't check logins is a mistake - refuse to start rather than run
    # unprotected.
    if settings.env in ("staging", "production"):
        # A deployed API that can't authenticate anyone is a misconfiguration: refuse to start.
        raise ConfigurationError("AUTH_JWKS_URL, AUTH_ISSUER and AUTH_AUDIENCE must be set")
    # Local development without login settings: no checker, so every /api/v1 call is refused
    # (fail closed).
    return None

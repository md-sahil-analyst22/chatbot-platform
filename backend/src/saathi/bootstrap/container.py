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

# From __future__ — Python language switches: annotations = lets type hints mention classes
#   defined later.
from __future__ import annotations

# From collections.abc — standard type names for collections: Awaitable = type for something you
#   can `await`; Callable = type for a function; Mapping = type for a read-only dictionary.
from collections.abc import Awaitable, Callable, Mapping

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# httpx — the HTTP client we use to call other web services.
import httpx

# From redis.asyncio — async client for Redis, the fast in-memory store: Redis = the Redis
#   client.
from redis.asyncio import Redis

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncEngine =
#   the async connection pool; AsyncSession = one unit of database work; async_sessionmaker =
#   factory that creates sessions.
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# Importing this file registers every vendor adapter (Gemini, Sarvam, Supabase...) in its phone
# book.
# From saathi.bootstrap — start-up wiring: providers = importing it registers every vendor
#   adapter.
from saathi.bootstrap import providers  # noqa: F401  (registers all adapters)

# From saathi.modules.tenancy.adapters.membership_lookup — login -> workspace lookup:
#   SqlAlchemyMembershipLookup = finds a user's workspace.
from saathi.modules.tenancy.adapters.membership_lookup import SqlAlchemyMembershipLookup

# From saathi.platform.config.model_catalog — the list of AI models tenants may choose:
#   ModelCatalog = the catalog; default_catalog = builds the catalog.
from saathi.platform.config.model_catalog import ModelCatalog, default_catalog

# From saathi.platform.config.settings — the app's core settings: Settings = the settings class.
from saathi.platform.config.settings import Settings

# From saathi.platform.db.engine — the database connection pool: build_engine = creates the
#   connection pool; build_sessionmaker = creates the session factory; ping_database = checks the
#   database answers.
from saathi.platform.db.engine import build_engine, build_sessionmaker, ping_database

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing.
from saathi.platform.errors import ConfigurationError

# From saathi.platform.http — the shared HTTP client: build_http_client = creates the shared
#   HTTP client.
from saathi.platform.http import build_http_client

# From saathi.platform.security.auth — who is calling and what they may do: TokenVerifier =
#   contract: check a login token.
from saathi.platform.security.auth import TokenVerifier

# From saathi.platform.security.jwt_verifier — the login-token checker: JwksTokenVerifier = the
#   real login checker.
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

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


# @dataclass writes the __init__ for us from the fields below; slots=True saves memory.
@dataclass(slots=True)
# The toolbox. `@dataclass` just means 'a class that mainly holds these fields'.
class Container:
    # The app's settings (from .env).
    settings: Settings
    # The database connection pool.
    engine: AsyncEngine
    # The factory that opens database sessions.
    sessionmaker: async_sessionmaker[AsyncSession]
    # The Redis client.
    redis: Redis
    # The shared HTTP client for calling vendors.
    http: httpx.AsyncClient
    # The list of AI models tenants may choose.
    model_catalog: ModelCatalog
    # The login checker (None = every /api/v1 call is refused).
    token_verifier: TokenVerifier | None

    # A classmethod is called on the class itself: Container.build(settings).
    @classmethod
    # Create every tool from the settings. Nothing connects yet - connections open on first use.
    def build(cls, settings: Settings) -> Container:
        # Create the database pool, using the secret DATABASE_URL.
        engine = build_engine(settings.database_url.get_secret_value())
        # Create the session factory on top of that pool.
        sessionmaker = build_sessionmaker(engine)
        # Create the shared HTTP client.
        http = build_http_client()
        # Create the container holding:
        return cls(
            # the settings,
            settings=settings,
            # the pool,
            engine=engine,
            # the session factory,
            sessionmaker=sessionmaker,
            # a Redis client (decode_responses=True gives text instead of raw bytes),
            redis=Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True),
            # the HTTP client,
            http=http,
            # the model catalog,
            model_catalog=default_catalog(),
            # and the login checker.
            token_verifier=build_token_verifier(settings, http, sessionmaker),
        )

    # Which checks /ready runs: can we reach the database and Redis?
    def readiness_checks(self) -> Mapping[str, Callable[[], Awaitable[object]]]:
        """Dependencies the API needs before it can serve traffic (used by /ready)."""
        # Two checks, by name: is the database answering, and is Redis answering?
        return {"database": self._ping_database, "redis": self._ping_redis}

    # One tiny `SELECT 1` round trip.
    async def _ping_database(self) -> None:
        # Run one tiny query against the database.
        await ping_database(self.engine)

    # One Redis PING.
    async def _ping_redis(self) -> None:
        # Ask Redis 'PING'; it answers 'PONG' if healthy.
        await self.redis.ping()

    # Close everything at shutdown, in reverse order of importance.
    async def aclose(self) -> None:
        # Close the HTTP client's open connections.
        await self.http.aclose()
        # Close the Redis connection.
        await self.redis.aclose()
        # Close every database connection in the pool.
        await self.engine.dispose()


# 🔒 Decide how logins are checked (ADR-0007).
def build_token_verifier(
    # the app settings,
    settings: Settings,
    # the HTTP client (to download Supabase's public keys),
    http: httpx.AsyncClient,
    # the session factory (to look up the user's workspace).
    sessionmaker: async_sessionmaker[AsyncSession],
) -> TokenVerifier | None:
    """ADR-0007. None means every /api/v1 call is refused (fail closed, R16)."""
    # Unpack the three login settings into three short names.
    url, issuer, audience = settings.auth_jwks_url, settings.auth_issuer, settings.auth_audience
    # All three login settings present: check Supabase tokens and look up the user's workspace.
    if url and issuer and audience:
        # Build the real login checker with:
        return JwksTokenVerifier(
            # the HTTP client,
            http,
            # where Supabase publishes its public keys,
            jwks_url=url,
            # who must have issued the token,
            issuer=issuer,
            # who the token must be meant for,
            audience=audience,
            # and how to find a user's workspace.
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

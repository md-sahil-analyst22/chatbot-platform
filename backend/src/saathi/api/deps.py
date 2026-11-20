# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 'Dependencies': small functions that hand a route exactly what it needs - who is
#       calling, a database session, the HTTP client...
# How it works: A route says e.g. `principal: PrincipalDep`; FastAPI runs get_principal() first
#               and passes the result in.
# Security: 🔒 get_principal and get_tenant_db are the doors of the API: no valid login = 401,
#           and every database session is locked to the caller's tenant.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Shared FastAPI dependencies - one narrow dependency per resource.

Endpoints ask for exactly what they use (a sessionmaker, a verifier, the HTTP client), never
the whole container. This file deliberately does NOT import saathi.bootstrap: the lifespan in
main.py publishes each resource on app.state, so modules that use these dependencies do not
transitively depend on every other module's adapters (import-linter enforces this).
"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# From typing — type-hint helpers: Annotated = a type plus extra info (e.g. a FastAPI
#   dependency).
from typing import Annotated

# httpx — the HTTP client we use to call other web services.
import httpx

# structlog — structured logging (JSON log lines).
import structlog

# From fastapi — the web framework that turns Python functions into web endpoints: Depends =
#   asks FastAPI to hand over a ready-made object (dependency injection); Request = the incoming
#   HTTP request.
from fastapi import Depends, Request

# From fastapi.security — helpers for reading login tokens: HTTPAuthorizationCredentials = the
#   token it read; HTTPBearer = reads the 'Authorization: Bearer <token>' header.
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncSession =
#   one unit of database work; async_sessionmaker = factory that creates sessions.
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# From saathi.platform.config.model_catalog — the list of AI models tenants may choose:
#   ModelCatalog = the catalog.
from saathi.platform.config.model_catalog import ModelCatalog

# From saathi.platform.db.tenant_context — locks a database session to one tenant:
#   tenant_session = a session locked to one tenant.
from saathi.platform.db.tenant_context import tenant_session

# From saathi.platform.errors — our error types: AuthenticationError = 401 not logged in.
from saathi.platform.errors import AuthenticationError

# From saathi.platform.security.auth — who is calling and what they may do: Principal = the
#   verified caller; TokenVerifier = contract: check a login token.
from saathi.platform.security.auth import Principal, TokenVerifier

# Reads the 'Authorization: Bearer <token>' header (without failing by itself if it's missing).
_bearer = HTTPBearer(auto_error=False)


# Gives the database session factory that main.py put on app.state.
async def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    # The session factory that main.py stored on the app at start-up.
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    # Hand it to whoever asked.
    return sessionmaker


# Gives the login checker (or None if login isn't configured).
async def get_token_verifier(request: Request) -> TokenVerifier | None:
    # The login checker stored at start-up (None if login isn't configured).
    verifier: TokenVerifier | None = request.app.state.token_verifier
    # Hand it over.
    return verifier


# Gives the list of AI models tenants may choose from.
async def get_model_catalog(request: Request) -> ModelCatalog:
    # The model catalog stored at start-up.
    catalog: ModelCatalog = request.app.state.model_catalog
    # Hand it over.
    return catalog


# Gives the one shared HTTP client for calling outside services.
async def get_http_client(request: Request) -> httpx.AsyncClient:
    # The shared HTTP client stored at start-up.
    http: httpx.AsyncClient = request.app.state.http
    # Hand it over.
    return http


# 🔒 Works out WHO is calling. Every /api/v1 route depends on this.
async def get_principal(
    # FastAPI supplies the login checker...
    verifier: Annotated[TokenVerifier | None, Depends(get_token_verifier)],
    # ...and the token from the 'Authorization: Bearer ...' header (None if missing).
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    # No token at all -> 401.
    if credentials is None:
        # Stop with 401.
        raise AuthenticationError("missing bearer token")
    # Login isn't configured on this server -> refuse everyone (fail closed).
    if verifier is None:  # fail closed until P1.7 wires a verifier
        # Stop with 401: never let anyone in when we can't check logins.
        raise AuthenticationError("authentication is not configured")
    # Check the token and find the user's workspace (platform/security/jwt_verifier.py).
    principal = await verifier.verify(credentials.credentials)
    # From now on, every log line of this request carries the tenant id.
    structlog.contextvars.bind_contextvars(tenant_id=str(principal.tenant_id))
    # Hand the verified caller to the endpoint.
    return principal


# Shortcut routes use to say 'I need the caller'.
PrincipalDep = Annotated[Principal, Depends(get_principal)]


# 🔒 A database session locked to the caller's tenant: Postgres then hides every other tenant's
# rows.
async def get_tenant_db(
    # FastAPI supplies the session factory...
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    # ...and the verified caller.
    principal: PrincipalDep,
) -> AsyncIterator[AsyncSession]:
    """DB session whose transaction is bound to the caller's tenant (RLS)."""
    # 🔒 Open a database session locked to the caller's tenant (row-level security).
    async with tenant_session(sessionmaker, principal.tenant_id) as session:
        # Lend the session to the endpoint; it is committed or rolled back afterwards.
        yield session


# Short name: endpoints write `db: TenantDbDep` to get a tenant-locked session.
TenantDbDep = Annotated[AsyncSession, Depends(get_tenant_db)]
# Short name: endpoints write `http: HttpClientDep` to get the shared HTTP client.
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]

"""Shared FastAPI dependencies - one narrow dependency per resource.

Endpoints ask for exactly what they use (a sessionmaker, a verifier, the HTTP client), never
the whole container. This file deliberately does NOT import saathi.bootstrap: the lifespan in
main.py publishes each resource on app.state, so modules that use these dependencies do not
transitively depend on every other module's adapters (import-linter enforces this).
"""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saathi.platform.config.model_catalog import ModelCatalog
from saathi.platform.db.tenant_context import tenant_session
from saathi.platform.errors import AuthenticationError
from saathi.platform.security.auth import Principal, TokenVerifier

_bearer = HTTPBearer(auto_error=False)


async def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    return sessionmaker


async def get_token_verifier(request: Request) -> TokenVerifier | None:
    verifier: TokenVerifier | None = request.app.state.token_verifier
    return verifier


async def get_model_catalog(request: Request) -> ModelCatalog:
    catalog: ModelCatalog = request.app.state.model_catalog
    return catalog


async def get_http_client(request: Request) -> httpx.AsyncClient:
    http: httpx.AsyncClient = request.app.state.http
    return http


async def get_principal(
    verifier: Annotated[TokenVerifier | None, Depends(get_token_verifier)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise AuthenticationError("missing bearer token")
    if verifier is None:  # fail closed until P1.7 wires a verifier
        raise AuthenticationError("authentication is not configured")
    principal = await verifier.verify(credentials.credentials)
    structlog.contextvars.bind_contextvars(tenant_id=str(principal.tenant_id))
    return principal


PrincipalDep = Annotated[Principal, Depends(get_principal)]


async def get_tenant_db(
    sessionmaker: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessionmaker)],
    principal: PrincipalDep,
) -> AsyncIterator[AsyncSession]:
    """DB session whose transaction is bound to the caller's tenant (RLS)."""
    async with tenant_session(sessionmaker, principal.tenant_id) as session:
        yield session


TenantDbDep = Annotated[AsyncSession, Depends(get_tenant_db)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]

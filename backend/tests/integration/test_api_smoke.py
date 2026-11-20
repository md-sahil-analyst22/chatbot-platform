# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Basic HTTP checks: /health works and protected endpoints refuse calls without
#                login.
# How to run: cd backend && uv run pytest tests/integration (no real database: services are
#             swapped for in-memory fakes).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""HTTP smoke tests. No DB needed: /health has no dependencies and auth fails closed first.

The lifespan is entered explicitly because httpx.ASGITransport does not run it. Building the
container does not open connections (engine and Redis client connect lazily).
"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From saathi.main — the FastAPI app factory: create_app = builds the FastAPI app.
from saathi.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_health_returns_ok_and_request_id(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert len(r.headers["x-request-id"]) >= 8


async def test_bots_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/bots", json={"name": "x", "languages": ["en"]})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


async def test_bots_fails_closed_without_verifier(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/v1/bots",
        json={"name": "x", "languages": ["en"]},
        headers={"Authorization": "Bearer anything"},
    )
    assert r.status_code == 401

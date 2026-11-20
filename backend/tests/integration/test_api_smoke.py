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


# A fixture: a test HTTP client talking to the real app in memory.
@pytest.fixture
# (created fresh for each test)
async def client() -> AsyncIterator[httpx.AsyncClient]:
    # Build the real app.
    app = create_app()
    # Run its start-up code (and shutdown code afterwards).
    async with app.router.lifespan_context(app):
        # Send requests straight into the app instead of over the network.
        transport = httpx.ASGITransport(app=app)
        # A client using that transport.
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            # Lend it to the test.
            yield c


# /health works and every response carries a request id.
async def test_health_returns_ok_and_request_id(client: httpx.AsyncClient) -> None:
    # GET /health.
    r = await client.get("/health")
    # 200 OK.
    assert r.status_code == 200
    # The body.
    assert r.json() == {"status": "ok"}
    # A request id header of at least 8 characters.
    assert len(r.headers["x-request-id"]) >= 8


# 🔒 Creating a bot without logging in is refused.
async def test_bots_requires_auth(client: httpx.AsyncClient) -> None:
    # POST without a token.
    r = await client.post("/api/v1/bots", json={"name": "x", "languages": ["en"]})
    # 401.
    assert r.status_code == 401
    # With our standard error code.
    assert r.json()["error"]["code"] == "unauthenticated"


# 🔒 With no login checker configured, even a token is refused.
async def test_bots_fails_closed_without_verifier(client: httpx.AsyncClient) -> None:
    # POST...
    r = await client.post(
        # to /api/v1/bots,
        "/api/v1/bots",
        # with a body,
        json={"name": "x", "languages": ["en"]},
        # and a made-up token.
        headers={"Authorization": "Bearer anything"},
    )
    # Still 401.
    assert r.status_code == 401

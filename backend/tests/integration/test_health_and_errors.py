# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: Health probes, the shared error format and the access log.
# How to run: cd backend && uv run pytest tests/integration (no real database: services are
#             swapped for in-memory fakes).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""P1.3: probes, the shared error shape for framework errors, and the access log.

Readiness checks are swapped for fakes after the lifespan starts, so no Postgres or Redis is
needed (the real ones are exercised by `make up` + /ready).
"""

# asyncio — runs many waiting tasks at once (async).
import asyncio

# logging — Python's built-in logging.
import logging

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# structlog — structured logging (JSON log lines).
import structlog

# From fastapi — the web framework that turns Python functions into web endpoints: FastAPI = the
#   web app object.
from fastapi import FastAPI

# From structlog.testing — structlog's test helpers: capture_logs = records logs so a test can
#   check them.
from structlog.testing import capture_logs

# From saathi.api — the HTTP layer shared by all modules: health = the health endpoints module.
from saathi.api import health

# From saathi.main — the FastAPI app factory: create_app = builds the FastAPI app.
from saathi.main import create_app


# A fixture: the real app with its start-up code run.
@pytest.fixture
# (created fresh for each test)
async def app() -> AsyncIterator[FastAPI]:
    # Build it.
    application = create_app()
    # Run start-up (and shutdown afterwards).
    async with application.router.lifespan_context(application):
        # Lend it to the test.
        yield application


# A fixture: an HTTP client talking to that app in memory.
@pytest.fixture
# (uses the app fixture above)
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # Send requests straight into the app.
    transport = httpx.ASGITransport(app=app)
    # A client using that transport.
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Lend it to the test.
        yield c


# A fake check that passes.
async def _ok() -> None:
    # Nothing to do.
    return None


# A fake check that fails with a message containing a password.
async def _boom() -> None:
    # Raise it.
    raise ConnectionError("could not connect to postgres://saathi_app:secret@db")


# A fake check that hangs.
async def _hang() -> None:
    # Wait 10 seconds (longer than the time limit).
    await asyncio.sleep(10)


# Start-up registers the database and Redis checks.
def test_lifespan_wires_database_and_redis_checks(app: FastAPI) -> None:
    # Exactly those two.
    assert set(app.state.readiness_checks) == {"database", "redis"}


# All checks pass -> 200 ready.
async def test_ready_when_all_checks_pass(app: FastAPI, client: httpx.AsyncClient) -> None:
    # Replace the checks with passing fakes.
    app.state.readiness_checks = {"database": _ok, "redis": _ok}
    # GET /ready.
    r = await client.get("/ready")
    # 200.
    assert r.status_code == 200
    # The body.
    assert r.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}
    # Not cacheable.
    assert r.headers["cache-control"] == "no-store"


# 🔒 A failing check -> 503, and no secret from the error leaks.
async def test_not_ready_when_a_check_fails_and_no_details_leak(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    # The database check fails.
    app.state.readiness_checks = {"database": _boom, "redis": _ok}
    # GET /ready.
    r = await client.get("/ready")
    # 503.
    assert r.status_code == 503
    # Which check failed.
    assert r.json() == {"status": "not_ready", "checks": {"database": "fail", "redis": "ok"}}
    # The password and address in the error message are not in the answer.
    assert "secret" not in r.text and "postgres" not in r.text


# A hanging check -> 503 instead of hanging the probe.
async def test_not_ready_when_a_check_hangs(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shrink the time limit to 0.05 s for this test.
    monkeypatch.setattr(health, "READY_TIMEOUT_SECONDS", 0.05)
    # The Redis check hangs.
    app.state.readiness_checks = {"database": _ok, "redis": _hang}
    # GET /ready.
    r = await client.get("/ready")
    # 503.
    assert r.status_code == 503
    # Redis reported as failed.
    assert r.json()["checks"]["redis"] == "fail"


# 🔒 No checks registered -> 503 (fail closed).
async def test_not_ready_fails_closed_without_checks(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    # No checks.
    app.state.readiness_checks = {}
    # GET /ready.
    r = await client.get("/ready")
    # 503.
    assert r.status_code == 503


# 🔒 The log names the error type but not its message.
async def test_failed_check_log_has_type_but_not_message(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    # A failing check.
    app.state.readiness_checks = {"database": _boom}
    # Capture log entries...
    with capture_logs() as logs:
        # ...while calling /ready.
        await client.get("/ready")
    # The 'check failed' entries.
    failed = [e for e in logs if e["event"] == "readiness.check_failed"]
    # Exactly one, with these fields only:
    assert failed == [
        # one entry:
        {
            # the event,
            "event": "readiness.check_failed",
            # the level,
            "log_level": "warning",
            # the check,
            "check": "database",
            # the error type (no message, so no password).
            "error": "ConnectionError",
        }
    ]


# Unknown URLs get our standard error shape.
async def test_unknown_route_uses_error_shape(client: httpx.AsyncClient) -> None:
    # GET a missing path with our own request id.
    r = await client.get("/does-not-exist", headers={"X-Request-ID": "req-12345678"})
    # 404.
    assert r.status_code == 404
    # The standard body, echoing our request id.
    assert r.json() == {
        "error": {"code": "not_found", "message": "Not found.", "request_id": "req-12345678"}
    }


# Wrong method -> 405 in our shape, keeping the Allow header.
async def test_wrong_method_uses_error_shape_and_keeps_allow_header(
    # (uses the client fixture)
    client: httpx.AsyncClient,
) -> None:
    # POST to a GET-only path.
    r = await client.post("/health")
    # 405.
    assert r.status_code == 405
    # Our error code.
    assert r.json()["error"]["code"] == "method_not_allowed"
    # The Allow header says GET.
    assert "GET" in r.headers["allow"]


# 🔒 The access log has method, path, status and time, but never the ?query part.
async def test_access_log_has_status_and_duration_but_no_query_string(
    # (uses the client fixture)
    client: httpx.AsyncClient,
) -> None:
    # Capture logs...
    with capture_logs() as logs:
        # ...for a request with a secret-looking query.
        await client.get("/does-not-exist?token=abc123")
    # The access-log entries.
    access = [e for e in logs if e["event"] == "http.request"]
    # Exactly one.
    assert len(access) == 1
    # Take it.
    entry = access[0]
    # Method, path (no query), status.
    assert (entry["method"], entry["path"], entry["status"]) == ("GET", "/does-not-exist", 404)
    # Logged at info.
    assert entry["log_level"] == "info"
    # Duration is a number.
    assert isinstance(entry["duration_ms"], float)
    # The query value is nowhere in it.
    assert "abc123" not in str(entry)


# Health-check requests are logged at debug (so they don't flood the logs).
async def test_probes_are_logged_at_debug(client: httpx.AsyncClient) -> None:
    # The app filters below INFO before any processor runs; let debug through for this test.
    previous = structlog.get_config()
    # Allow debug-level entries for this test.
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG))
    # Try...
    try:
        # ...capturing logs...
        with capture_logs() as logs:
            # ...for GET /health.
            await client.get("/health")
    # Always...
    finally:
        # ...restore the previous logging set-up.
        structlog.configure(**previous)
    # The access-log entry was at debug level.
    assert [e["log_level"] for e in logs if e["event"] == "http.request"] == ["debug"]

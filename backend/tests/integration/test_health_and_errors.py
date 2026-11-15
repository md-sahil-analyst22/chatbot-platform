"""P1.3: probes, the shared error shape for framework errors, and the access log.

Readiness checks are swapped for fakes after the lifespan starts, so no Postgres or Redis is
needed (the real ones are exercised by `make up` + /ready).
"""

import asyncio
import logging
from collections.abc import AsyncIterator

import httpx
import pytest
import structlog
from fastapi import FastAPI
from structlog.testing import capture_logs

from saathi.api import health
from saathi.main import create_app


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    application = create_app()
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _ok() -> None:
    return None


async def _boom() -> None:
    raise ConnectionError("could not connect to postgres://saathi_app:secret@db")


async def _hang() -> None:
    await asyncio.sleep(10)


def test_lifespan_wires_database_and_redis_checks(app: FastAPI) -> None:
    assert set(app.state.readiness_checks) == {"database", "redis"}


async def test_ready_when_all_checks_pass(app: FastAPI, client: httpx.AsyncClient) -> None:
    app.state.readiness_checks = {"database": _ok, "redis": _ok}
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}
    assert r.headers["cache-control"] == "no-store"


async def test_not_ready_when_a_check_fails_and_no_details_leak(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    app.state.readiness_checks = {"database": _boom, "redis": _ok}
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "not_ready", "checks": {"database": "fail", "redis": "ok"}}
    assert "secret" not in r.text and "postgres" not in r.text


async def test_not_ready_when_a_check_hangs(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "READY_TIMEOUT_SECONDS", 0.05)
    app.state.readiness_checks = {"database": _ok, "redis": _hang}
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["redis"] == "fail"


async def test_not_ready_fails_closed_without_checks(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    app.state.readiness_checks = {}
    r = await client.get("/ready")
    assert r.status_code == 503


async def test_failed_check_log_has_type_but_not_message(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    app.state.readiness_checks = {"database": _boom}
    with capture_logs() as logs:
        await client.get("/ready")
    failed = [e for e in logs if e["event"] == "readiness.check_failed"]
    assert failed == [
        {
            "event": "readiness.check_failed",
            "log_level": "warning",
            "check": "database",
            "error": "ConnectionError",
        }
    ]


async def test_unknown_route_uses_error_shape(client: httpx.AsyncClient) -> None:
    r = await client.get("/does-not-exist", headers={"X-Request-ID": "req-12345678"})
    assert r.status_code == 404
    assert r.json() == {
        "error": {"code": "not_found", "message": "Not found.", "request_id": "req-12345678"}
    }


async def test_wrong_method_uses_error_shape_and_keeps_allow_header(
    client: httpx.AsyncClient,
) -> None:
    r = await client.post("/health")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "method_not_allowed"
    assert "GET" in r.headers["allow"]


async def test_access_log_has_status_and_duration_but_no_query_string(
    client: httpx.AsyncClient,
) -> None:
    with capture_logs() as logs:
        await client.get("/does-not-exist?token=abc123")
    access = [e for e in logs if e["event"] == "http.request"]
    assert len(access) == 1
    entry = access[0]
    assert (entry["method"], entry["path"], entry["status"]) == ("GET", "/does-not-exist", 404)
    assert entry["log_level"] == "info"
    assert isinstance(entry["duration_ms"], float)
    assert "abc123" not in str(entry)


async def test_probes_are_logged_at_debug(client: httpx.AsyncClient) -> None:
    # The app filters below INFO before any processor runs; let debug through for this test.
    previous = structlog.get_config()
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG))
    try:
        with capture_logs() as logs:
            await client.get("/health")
    finally:
        structlog.configure(**previous)
    assert [e["log_level"] for e in logs if e["event"] == "http.request"] == ["debug"]

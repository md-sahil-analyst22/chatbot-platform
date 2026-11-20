# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Two check-up URLs used by the server and uptime monitors.
# /health: 'Is the app alive?' Always fast; never touches the database.
# /ready: 'Can the app serve traffic right now?' Checks the database and Redis, 2 seconds each.
# Security: 🔒 Both answer only ok/fail - never error messages, which could reveal addresses or
#           passwords.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Probes for the deploy platform and uptime monitors (unversioned, no login).

- /health: liveness. No dependency calls, so it stays fast and never cascades failures.
  A failing /health means "restart me".
- /ready: readiness. Checks every dependency the API needs (database, Redis). A failing /ready
  means "don't send me traffic yet", not "restart me".

Neither endpoint ever returns error messages or connection details: only "ok" / "fail".
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

# How long one readiness check may take before it counts as failed.
READY_TIMEOUT_SECONDS = 2.0

ReadinessCheck = Callable[[], Awaitable[object]]


# GET /health -> {"status": "ok"}.
@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Runs one check (e.g. 'database') with the time limit and reports True/False.
async def _run(name: str, check: ReadinessCheck) -> tuple[str, bool]:
    try:
        await asyncio.wait_for(check(), timeout=READY_TIMEOUT_SECONDS)
    # Any failure means 'not ready'. Only the error TYPE is logged, never its message (it could
    # contain secrets).
    except Exception as exc:  # any failure means "not ready"; never crash the probe
        # Exception type only: messages can contain hosts or credentials (R17).
        structlog.get_logger().warning(
            "readiness.check_failed", check=name, error=type(exc).__name__
        )
        return name, False
    return name, True


# GET /ready -> 200 ready, or 503 not_ready with which check failed.
@router.get("/ready", response_model=None)
async def ready(request: Request) -> JSONResponse:
    # The checks were put on app.state at start-up by the container (database, redis).
    checks: Mapping[str, ReadinessCheck] = getattr(request.app.state, "readiness_checks", {})
    # No checks configured? Say 'not ready' rather than pretend (fail closed).
    if not checks:  # fail closed: nothing wired means we can't prove readiness (R16)
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": {}})
    # Run all checks at the same time, so /ready stays fast.
    results = await asyncio.gather(*(_run(name, check) for name, check in checks.items()))
    all_ok = all(ok for _, ok in results)
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": {name: "ok" if ok else "fail" for name, ok in results},
        },
        headers={"Cache-Control": "no-store"},
    )

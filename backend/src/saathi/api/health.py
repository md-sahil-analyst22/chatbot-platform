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

# asyncio — runs many waiting tasks at once (async).
import asyncio

# From collections.abc — standard type names for collections: Awaitable = type for something you
#   can `await`; Callable = type for a function; Mapping = type for a read-only dictionary.
from collections.abc import Awaitable, Callable, Mapping

# structlog — structured logging (JSON log lines).
import structlog

# From fastapi — the web framework that turns Python functions into web endpoints: APIRouter = a
#   group of related endpoints; Request = the incoming HTTP request.
from fastapi import APIRouter, Request

# From fastapi.responses — ready-made HTTP responses: JSONResponse = an HTTP response with a
#   JSON body.
from fastapi.responses import JSONResponse

# A group for the health endpoints (shown under 'health' in the docs).
router = APIRouter(tags=["health"])

# How long one readiness check may take before it counts as failed.
READY_TIMEOUT_SECONDS = 2.0

# Type name: a readiness check is a function you can `await` (e.g. a database ping).
ReadinessCheck = Callable[[], Awaitable[object]]


# GET /health -> {"status": "ok"}.
@router.get("/health")
# GET /health: 'the process is alive'. It touches nothing else, so it's always fast.
async def health() -> dict[str, str]:
    # Always answer {"status": "ok"}.
    return {"status": "ok"}


# Runs one check (e.g. 'database') with the time limit and reports True/False.
async def _run(name: str, check: ReadinessCheck) -> tuple[str, bool]:
    # Try the check...
    try:
        # ...but give up after READY_TIMEOUT_SECONDS so a hung database can't hang the probe.
        await asyncio.wait_for(check(), timeout=READY_TIMEOUT_SECONDS)
    # Any failure means 'not ready'. Only the error TYPE is logged, never its message (it could
    # contain secrets).
    except Exception as exc:  # any failure means "not ready"; never crash the probe
        # Exception type only: messages can contain hosts or credentials (R17).
        structlog.get_logger().warning(
            "readiness.check_failed", check=name, error=type(exc).__name__
        )
        # Report this check as failed.
        return name, False
    # The check passed.
    return name, True


# GET /ready -> 200 ready, or 503 not_ready with which check failed.
@router.get("/ready", response_model=None)
# GET /ready: 'can this server do real work right now?' (database and Redis answer).
async def ready(request: Request) -> JSONResponse:
    # The checks were put on app.state at start-up by the container (database, redis).
    checks: Mapping[str, ReadinessCheck] = getattr(request.app.state, "readiness_checks", {})
    # No checks configured? Say 'not ready' rather than pretend (fail closed).
    if not checks:  # fail closed: nothing wired means we can't prove readiness (R16)
        # Answer 503 'not ready' with no checks.
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": {}})
    # Run all checks at the same time, so /ready stays fast.
    results = await asyncio.gather(*(_run(name, check) for name, check in checks.items()))
    # Ready only if every single check passed.
    all_ok = all(ok for _, ok in results)
    # Build the answer.
    return JSONResponse(
        # 200 = ready, 503 = not ready (load balancers stop sending traffic on 503).
        status_code=200 if all_ok else 503,
        # The JSON body:
        content={
            # overall status...
            "status": "ready" if all_ok else "not_ready",
            # ...and ok/fail per check, e.g. {"database": "ok", "redis": "fail"}.
            "checks": {name: "ok" if ok else "fail" for name, ok in results},
        },
        # Never cache this answer; it must be fresh every time.
        headers={"Cache-Control": "no-store"},
    )

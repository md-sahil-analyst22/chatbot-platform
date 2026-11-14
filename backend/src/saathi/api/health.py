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

READY_TIMEOUT_SECONDS = 2.0

ReadinessCheck = Callable[[], Awaitable[object]]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _run(name: str, check: ReadinessCheck) -> tuple[str, bool]:
    try:
        await asyncio.wait_for(check(), timeout=READY_TIMEOUT_SECONDS)
    except Exception as exc:  # any failure means "not ready"; never crash the probe
        # Exception type only: messages can contain hosts or credentials (R17).
        structlog.get_logger().warning(
            "readiness.check_failed", check=name, error=type(exc).__name__
        )
        return name, False
    return name, True


@router.get("/ready", response_model=None)
async def ready(request: Request) -> JSONResponse:
    checks: Mapping[str, ReadinessCheck] = getattr(request.app.state, "readiness_checks", {})
    if not checks:  # fail closed: nothing wired means we can't prove readiness (R16)
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": {}})
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

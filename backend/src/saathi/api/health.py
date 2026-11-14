from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness only - no dependency calls, so it stays fast and never cascades failures.

    A readiness probe (/ready: DB + Redis checks) is added in Phase 1 for the deploy platform.
    """
    return {"status": "ok"}

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Background job that will process one uploaded document (runs in the worker, not the
#       API).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""ARQ job: ingest one source. Must be idempotent and tenant scoped."""

# From typing — type-hint helpers: Any = any type.
from typing import Any

# structlog — structured logging (JSON log lines).
import structlog

log = structlog.get_logger()


# Called by the worker with the tenant and source id; tags logs with both.
async def ingest_source(ctx: dict[str, Any], tenant_id: str, source_id: str) -> None:
    """Placeholder for P2.2. Re-running the same job must not duplicate chunks (hash check)."""
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id, source_id=source_id)
    log.info("ingest.started")
    # Phase 2: open tenant_session(...), call application.ingestion with injected ports.
    log.info("ingest.noop", reason="not implemented until Phase 2")

"""ARQ job: ingest one source. Must be idempotent and tenant scoped."""

from typing import Any

import structlog

log = structlog.get_logger()


async def ingest_source(ctx: dict[str, Any], tenant_id: str, source_id: str) -> None:
    """Placeholder for P2.2. Re-running the same job must not duplicate chunks (hash check)."""
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id, source_id=source_id)
    log.info("ingest.started")
    # Phase 2: open tenant_session(...), call application.ingestion with injected ports.
    log.info("ingest.noop", reason="not implemented until Phase 2")

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The background job that processes one source (runs in the worker, not the API), P2.2.
# How: the worker's startup (saathi/worker.py) builds an IngestionService and puts it in `ctx`;
#      this job only checks its inputs, tags the logs, runs the service and turns a temporary
#      provider failure into a delayed retry.
# Retries: bounded by WorkerSettings.max_tries; the wait doubles each time (10 s, 20 s, 40 s...,
#      at most 5 minutes) plus a little randomness so many jobs don't retry at the same moment.
# Safe to run twice: the service locks the source row and skips work that is already done (R33).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""ARQ job: ingest one source. Idempotent and tenant scoped."""

# random — jitter for retry delays (not security-relevant).
import random

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# structlog — structured logging (JSON log lines).
import structlog

# From arq — the job queue library: Retry = 'run this job again after a delay'.
from arq import Retry

# From saathi.modules.knowledge.application.ingestion — the use case: IngestOutcome = what
#   happened; IngestionService = processes one source.
from saathi.modules.knowledge.application.ingestion import IngestionService, IngestOutcome

# The logger for this file.
log = structlog.get_logger()

# First retry delay (seconds); doubles each attempt.
_BASE_DELAY_S = 10
# Longest retry delay (seconds).
_MAX_DELAY_S = 300


# How long to wait before attempt number `attempt + 1`.
def retry_delay_seconds(attempt: int) -> float:
    """Exponential backoff with jitter: 10, 20, 40, 80, 160, then 300 s max, plus 0-5 s."""
    # Doubling delay, capped.
    delay = float(min(_MAX_DELAY_S, _BASE_DELAY_S * 2 ** max(0, attempt - 1)))
    # Add jitter so jobs that failed together don't retry together.
    return delay + random.uniform(0, 5)  # noqa: S311 - jitter, not cryptography


# Called by the worker with the tenant and source id; tags logs with both.
async def ingest_source(
    ctx: dict[str, Any], tenant_id: str, source_id: str, request_id: str | None = None
) -> str:
    """Process one source. Re-running the same job never duplicates chunks."""
    # Tag every log line of this job with the tenant, the source and the original request.
    structlog.contextvars.bind_contextvars(
        tenant_id=tenant_id, source_id=source_id, request_id=request_id
    )
    # 🔒 The ids come from our own queue, but check them anyway (fail closed on garbage).
    try:
        # Parse both ids.
        tenant, source = UUID(tenant_id), UUID(source_id)
    # Not valid ids.
    except ValueError:
        # Log and drop the job (retrying can't fix it).
        log.warning("ingest.bad_job_arguments")
        # Report.
        return "invalid"
    # Which attempt this is (ARQ counts from 1).
    attempt = int(ctx.get("job_try", 1))
    # The service built at worker startup.
    service: IngestionService = ctx["ingestion"]
    # Log the start.
    log.info("ingest.started", attempt=attempt)
    # Run the use case.
    outcome = await service.ingest(
        tenant, source, attempt=attempt, max_attempts=int(ctx.get("max_tries", 1))
    )
    # Log the result.
    log.info("ingest.finished", outcome=outcome.value, attempt=attempt)
    # A temporary provider problem: ask ARQ to run this job again later.
    if outcome is IngestOutcome.RETRY:
        # Delayed retry (ARQ stops after max_tries).
        raise Retry(defer=retry_delay_seconds(attempt))
    # Done (ARQ stores this short result string).
    return outcome.value

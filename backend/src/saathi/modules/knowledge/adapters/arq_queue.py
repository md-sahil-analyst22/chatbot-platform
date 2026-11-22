# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Puts 'ingest this source' jobs on the ARQ (Redis) queue (implements IngestQueue).
# Inside a web request: the job is only sent AFTER the database transaction commits (via
#   AfterCommit), so the worker never looks for a row that isn't saved yet, and a rolled-back
#   request never leaves a job behind.
# Inside the worker: there is no request transaction, so jobs are sent straight away (the
#   worker calls it after its own commit).
# The request id travels with the job so one upload can be followed end to end in the logs.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""ARQ adapter for the ingestion queue."""

# From typing — type-hint helpers: Any = any type (ARQ has no type hints).
from typing import Any

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# structlog — structured logging (reads the current request id).
import structlog

# From saathi.platform.db.after_commit — after-commit hooks: AfterCommit = run work after COMMIT.
from saathi.platform.db.after_commit import AfterCommit

# The worker function's name (saathi.worker.WorkerSettings.functions).
INGEST_JOB = "ingest_source"


# The queue adapter.
class ArqIngestQueue:
    """Implements IngestQueue on an ArqRedis pool."""

    # Keep the pool and (in requests) the after-commit list.
    def __init__(self, pool: Any, after_commit: AfterCommit | None = None) -> None:
        # The ArqRedis connection pool (shared, created by the container).
        self._pool = pool
        # Request-scoped after-commit list; None in the worker.
        self._after_commit = after_commit

    # Queue one ingestion job.
    async def enqueue_ingest(self, tenant_id: UUID, source_id: UUID) -> None:
        # The current request id (if any), so the job's logs can be joined with the request's.
        request_id = structlog.contextvars.get_contextvars().get("request_id")

        # The actual send.
        async def send() -> None:
            # Positional args = tenant and source ids as text; the worker re-checks everything.
            await self._pool.enqueue_job(
                INGEST_JOB, str(tenant_id), str(source_id), request_id=request_id
            )

        # In a request: send after commit.
        if self._after_commit is not None:
            # Register it.
            self._after_commit.add(send)
        # In the worker: send now.
        else:
            # Send.
            await send()

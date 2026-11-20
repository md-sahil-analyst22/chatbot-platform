# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The background worker: a separate program that runs slow jobs (like reading a PDF) so
#       the API never makes a user wait.
# How it runs: Started with `arq saathi.worker.WorkerSettings`. It takes jobs from a queue in
#              Redis, one by one.
# Status: Phase 1 has only a placeholder job (ingest_source); real document processing arrives
#         in Phase 2.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""ARQ worker entry point: arq saathi.worker.WorkerSettings

Runs background jobs (ingestion, webhooks retries, rollups) outside the request path.
"""

from typing import Any, ClassVar

from arq.connections import RedisSettings

from saathi.modules.knowledge.workers.ingest_job import ingest_source
from saathi.platform.config.settings import get_settings


# Runs once when the worker starts: load the settings so jobs can use them.
async def startup(ctx: dict[str, Any]) -> None:
    ctx["settings"] = get_settings()


# Runs once when the worker stops. Nothing to clean up yet.
async def shutdown(ctx: dict[str, Any]) -> None:
    return None


# ARQ (the job runner) reads this class to know which jobs exist and how to run them.
class WorkerSettings:
    # The list of jobs this worker can run.
    functions: ClassVar[list[Any]] = [ingest_source]
    on_startup = startup
    on_shutdown = shutdown
    # Where the job queue lives (Redis address from the settings).
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url.get_secret_value())
    max_tries = 5  # bounded retries; failures are recorded on the source row
    job_timeout = 600  # seconds; a 30-page PDF must finish well under this
    # At most 10 jobs run at the same time.
    max_jobs = 10

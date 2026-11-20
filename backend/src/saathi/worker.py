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

# From typing — type-hint helpers: Any = any type; ClassVar = a class-level constant.
from typing import Any, ClassVar

# From arq.connections — ARQ, the background-job runner that uses Redis: RedisSettings = where
#   the job queue's Redis lives.
from arq.connections import RedisSettings

# From saathi.modules.knowledge.workers.ingest_job — the document-processing background job:
#   ingest_source = the job function.
from saathi.modules.knowledge.workers.ingest_job import ingest_source

# From saathi.platform.config.settings — the app's core settings: get_settings = the settings,
#   read once.
from saathi.platform.config.settings import get_settings


# Runs once when the worker starts: load the settings so jobs can use them.
async def startup(ctx: dict[str, Any]) -> None:
    # Load the settings once and keep them in the worker's shared `ctx` dictionary for every
    #   job.
    ctx["settings"] = get_settings()


# Runs once when the worker stops. Nothing to clean up yet.
async def shutdown(ctx: dict[str, Any]) -> None:
    # Nothing to clean up yet.
    return None


# ARQ (the job runner) reads this class to know which jobs exist and how to run them.
class WorkerSettings:
    # The list of jobs this worker can run.
    functions: ClassVar[list[Any]] = [ingest_source]
    # Run startup() when the worker starts.
    on_startup = startup
    # Run shutdown() when the worker stops.
    on_shutdown = shutdown
    # Where the job queue lives (Redis address from the settings).
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url.get_secret_value())
    max_tries = 5  # bounded retries; failures are recorded on the source row
    job_timeout = 600  # seconds; a 30-page PDF must finish well under this
    # At most 10 jobs run at the same time.
    max_jobs = 10

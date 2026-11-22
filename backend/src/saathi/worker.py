# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The background worker: a separate program that runs slow jobs (like reading a PDF) so
#       the API never makes a user wait.
# How it runs: Started with `arq saathi.worker.WorkerSettings`. It takes jobs from a queue in
#              Redis, one by one.
# Jobs: ingest_source (Phase 2) - read, clean, chunk and embed one uploaded file or website.
# Safety: jobs are bounded (max_tries, job_timeout) and safe to run twice (R33).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""ARQ worker entry point: arq saathi.worker.WorkerSettings

Runs background jobs (ingestion, webhooks retries, rollups) outside the request path.
"""

# From typing — type-hint helpers: Any = any type; ClassVar = a class-level constant.
from typing import Any, ClassVar

# From arq.connections — ARQ, the background-job runner that uses Redis: RedisSettings = where
#   the job queue's Redis lives.
from arq.connections import RedisSettings

# From saathi.bootstrap.container — process-wide resources: Container = DB pool, Redis, HTTP
#   client and vendor clients, built once.
from saathi.bootstrap.container import Container

# From saathi.bootstrap.knowledge_bridge — Phase 2 wiring: build_ingestion_service = the
#   ingestion use case with its adapters.
from saathi.bootstrap.knowledge_bridge import build_ingestion_service

# From saathi.modules.knowledge.workers.ingest_job — the document-processing background job:
#   ingest_source = the job function.
from saathi.modules.knowledge.workers.ingest_job import ingest_source

# From saathi.platform.config.settings — the app's core settings: get_settings = the settings,
#   read once.
from saathi.platform.config.settings import get_settings


# Runs once when the worker starts: settings, shared resources and the ingestion use case.
async def startup(ctx: dict[str, Any]) -> None:
    # Load the settings once and keep them in the worker's shared `ctx` dictionary for every
    #   job.
    ctx["settings"] = settings = get_settings()
    # Build the shared toolbox once (database pool, Redis, HTTP client, vendors).
    ctx["container"] = container = Container.build(settings)
    # The retry bound, so jobs know when they're on their last attempt.
    ctx["max_tries"] = WorkerSettings.max_tries
    # The ingestion use case. The worker can't do anything useful without storage, parsers,
    #   crawler and embedder, so they are built NOW: missing settings stop the worker at startup
    #   with a clear ConfigurationError (fail fast, R16) instead of failing every job.
    ctx["ingestion"] = build_ingestion_service(
        sessionmaker=container.sessionmaker,
        store=container.document_store(),
        parsers=container.parsers(),
        crawler=container.crawler(),
        embedder=container.embedder(),
        pool=container.job_pool,
    )


# Runs once when the worker stops.
async def shutdown(ctx: dict[str, Any]) -> None:
    # Close every connection cleanly (database pool, Redis, HTTP client), if startup got that far.
    container = ctx.get("container")
    # Only if it was built.
    if container is not None:
        # Close it.
        await container.aclose()


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
    # At most 4 jobs at the same time: parsing/OCR is CPU- and memory-heavy and the VPS is shared
    #   with n8n (ADR-0008). Scaling unit: worker replicas x max_jobs (and their DB connections).
    max_jobs = 4

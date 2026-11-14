"""ARQ worker entry point: arq saathi.worker.WorkerSettings

Runs background jobs (ingestion, webhooks retries, rollups) outside the request path.
"""

from typing import Any, ClassVar

from arq.connections import RedisSettings

from saathi.modules.knowledge.workers.ingest_job import ingest_source
from saathi.platform.config.settings import get_settings


async def startup(ctx: dict[str, Any]) -> None:
    ctx["settings"] = get_settings()


async def shutdown(ctx: dict[str, Any]) -> None:
    return None


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ingest_source]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url.get_secret_value())
    max_tries = 5  # bounded retries; failures are recorded on the source row
    job_timeout = 600  # seconds; a 30-page PDF must finish well under this
    max_jobs = 10

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The Phase 2 plumbing: after-commit callbacks, the publish hook call in
#                BotConfigService, the bootstrap bridges, the worker job's retry mapping, and
#                the extension -> parser map.
# How to run: cd backend && uv run pytest tests/unit/test_phase2_wiring.py (no database).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""AfterCommit, publish hook, bridges, ingest job."""

# From dataclasses — replace = copy with some fields changed.
from dataclasses import replace

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# pytest — the test framework.
import pytest

# From arq — the job queue library: Retry = 'run this job again later'.
from arq import Retry

# From tests.fakes.builders — test builders: NOW = a fixed time; make_bot, make_catalog,
#   make_config.
from tests.fakes.builders import NOW, make_bot, make_catalog, make_config

# From tests.fakes.in_memory — in-memory tenancy stores.
from tests.fakes.in_memory import (
    InMemoryBotConfigRepository,
    InMemoryBotRepository,
    InMemoryTenantRepository,
)

# From tests.fakes.knowledge — in-memory chunk and FAQ stores.
from tests.fakes.knowledge import InMemoryChunkRepository, InMemoryFaqRepository

# From tests.fakes.providers — FakeEmbedder; FakeReranker.
from tests.fakes.providers import FakeEmbedder, FakeReranker

# From saathi.bootstrap.knowledge_bridge — bridges: KnowledgeRetrieverAdapter = conversation's
#   retriever backed by knowledge; chunking_policy_from = settings -> ChunkingPolicy.
from saathi.bootstrap.knowledge_bridge import KnowledgeRetrieverAdapter, chunking_policy_from

# From saathi.bootstrap.providers — build_parsers_by_extension = '.pdf' -> parser map.
from saathi.bootstrap.providers import build_parsers_by_extension

# From saathi.modules.conversation.ports.retrieval — RetrievalRequest = search knobs.
from saathi.modules.conversation.ports.retrieval import RetrievalRequest

# From saathi.modules.knowledge.application.ingestion — IngestOutcome = what a job did.
from saathi.modules.knowledge.application.ingestion import IngestOutcome

# From saathi.modules.knowledge.application.retrieval — KnowledgeSearchService = the lookup.
from saathi.modules.knowledge.application.retrieval import KnowledgeSearchService

# From saathi.modules.knowledge.workers.ingest_job — the job: ingest_source; retry_delay_seconds.
from saathi.modules.knowledge.workers.ingest_job import ingest_source, retry_delay_seconds

# From saathi.modules.tenancy.application.config_service — BotConfigService = save/publish.
from saathi.modules.tenancy.application.config_service import BotConfigService

# From saathi.modules.tenancy.domain.bot_config — BotConfig; RetrievalSettings.
from saathi.modules.tenancy.domain.bot_config import BotConfig, RetrievalSettings

# From saathi.platform.db.after_commit — AfterCommit = work run after COMMIT.
from saathi.platform.db.after_commit import AfterCommit

# From saathi.platform.security.auth — Principal; Role.
from saathi.platform.security.auth import Principal, Role

# The test tenant.
TENANT = uuid4()


# After-commit work runs in order, survives a failing item, and runs only once.
async def test_after_commit_runs_in_order_survives_failures_and_runs_once() -> None:
    # Names of the callbacks that ran.
    ran: list[str] = []
    # A fresh list.
    hooks = AfterCommit()

    # A callback that records its name.
    async def ok(name: str) -> None:
        # Record.
        ran.append(name)

    # A callback that fails (like Redis being down).
    async def boom() -> None:
        # Fail.
        raise RuntimeError("redis down")

    # First callback.
    hooks.add(lambda: ok("first"))
    # A failing one in the middle.
    hooks.add(boom)
    # Third callback.
    hooks.add(lambda: ok("third"))
    # Three are waiting.
    assert len(hooks) == 3
    # 'Commit': run them.
    await hooks.run()
    # The failure was logged; the others still ran, in order.
    assert ran == ["first", "third"]
    # Adding after the run is a programming error (it would silently never run)...
    with pytest.raises(RuntimeError):
        # ...so it is refused.
        hooks.add(lambda: ok("late"))


# Records publish reactions.
class RecordingHook:
    """A ConfigPublishedHook that remembers its calls."""

    # Start with no calls.
    def __init__(self) -> None:
        # (tenant, bot, previous config, current config) per publish.
        self.calls: list[tuple[UUID, UUID, BotConfig | None, BotConfig]] = []

    # React to a publish.
    async def on_published(
        self, tenant_id: UUID, bot_id: UUID, previous: BotConfig | None, current: BotConfig
    ) -> None:
        # Remember it.
        self.calls.append((tenant_id, bot_id, previous, current))


# Publishing tells the hook what was live before and what is live now.
async def test_publish_calls_the_hook_with_previous_and_current_config() -> None:
    # Bot store, config store, hook.
    bots, configs, hook = InMemoryBotRepository(), InMemoryBotConfigRepository(), RecordingHook()
    # A bot of the test tenant...
    bot = make_bot(tenant_id=TENANT)
    # ...saved.
    await bots.add(bot)
    # The real service with the hook.
    service = BotConfigService(
        bots=bots,
        configs=configs,
        tenants=InMemoryTenantRepository({TENANT: "starter"}),
        catalog=make_catalog(),
        clock=lambda: NOW,
        publish_hook=hook,
    )
    # An admin.
    admin = Principal(user_id="u", tenant_id=TENANT, role=Role.ADMIN)
    # The first config.
    first = make_config()
    # A second config with a different chunk size.
    second = replace(first, retrieval=RetrievalSettings(chunk_size_tokens=500))
    # Save the first...
    await service.save_draft(admin, bot.id, first)
    # ...publish it.
    await service.publish(admin, bot.id)
    # Save the second...
    await service.save_draft(admin, bot.id, second)
    # ...publish it.
    await service.publish(admin, bot.id)
    # First publish: no previous; second: previous = first.
    assert [(c[2], c[3]) for c in hook.calls] == [(None, first), (first, second)]
    # Always the right tenant and bot.
    assert all(c[0] == TENANT and c[1] == bot.id for c in hook.calls)


# Tenancy's settings convert to knowledge's policy; their ranges agree.
def test_chunking_policy_conversion_matches_settings() -> None:
    # Convert custom settings.
    policy = chunking_policy_from(RetrievalSettings(chunk_size_tokens=650, chunk_overlap_ratio=0.2))
    # Same two numbers.
    assert (policy.chunk_size_tokens, policy.overlap_ratio) == (650, 0.2)
    # The smallest values tenancy accepts are accepted by knowledge too...
    chunking_policy_from(RetrievalSettings(chunk_size_tokens=200, chunk_overlap_ratio=0.0))
    # ...and so are the largest.
    chunking_policy_from(RetrievalSettings(chunk_size_tokens=1200, chunk_overlap_ratio=0.3))


# The retriever bridge converts an empty lookup into conversation's empty result.
async def test_retriever_adapter_maps_an_empty_lookup() -> None:
    # A lookup over empty stores.
    search = KnowledgeSearchService(
        chunks=InMemoryChunkRepository(),
        faqs=InMemoryFaqRepository(),
        embedder=FakeEmbedder(),
        reranker=FakeReranker(),
    )
    # Ask through the bridge.
    result = await KnowledgeRetrieverAdapter(search).retrieve(
        TENANT, uuid4(), "hi", RetrievalRequest()
    )
    # No FAQ, no passages, not reranked.
    assert result.faq is None and result.passages == [] and result.reranked is False


# An ingestion service stand-in with a fixed outcome.
class FakeIngestion:
    """Returns a fixed outcome and remembers its arguments."""

    # Keep the outcome.
    def __init__(self, outcome: IngestOutcome) -> None:
        # What ingest() returns.
        self.outcome = outcome
        # The arguments of the last call.
        self.args: tuple[Any, ...] = ()

    # Same signature as IngestionService.ingest.
    async def ingest(
        self, tenant_id: UUID, source_id: UUID, *, attempt: int, max_attempts: int
    ) -> IngestOutcome:
        # Remember the arguments.
        self.args = (tenant_id, source_id, attempt, max_attempts)
        # The fixed outcome.
        return self.outcome


# The job passes the attempt numbers on, retries on RETRY, drops garbage ids.
async def test_ingest_job_maps_outcomes() -> None:
    # A tenant and a source id.
    tid, sid = uuid4(), uuid4()
    # A service that always succeeds.
    done = FakeIngestion(IngestOutcome.DONE)
    # Attempt 2 of 5 -> 'done'.
    assert (
        await ingest_source({"ingestion": done, "job_try": 2, "max_tries": 5}, str(tid), str(sid))
        == "done"
    )
    # The ids (parsed) and attempt numbers reached the service.
    assert done.args == (tid, sid, 2, 5)
    # A temporary provider problem becomes a delayed ARQ retry...
    with pytest.raises(Retry):
        # ...raised by the job.
        await ingest_source({"ingestion": FakeIngestion(IngestOutcome.RETRY)}, str(tid), str(sid))
    # 🔒 Garbage ids are dropped (never retried, never reach the database).
    assert await ingest_source({"ingestion": done}, "not-a-uuid", str(sid)) == "invalid"


# Retry waits double each time and are capped.
def test_retry_delay_grows_and_is_capped() -> None:
    # First retry: 10 s + up to 5 s jitter.
    assert 10 <= retry_delay_seconds(1) <= 15
    # Second: 20 s + jitter.
    assert 20 <= retry_delay_seconds(2) <= 25
    # Never more than 5 minutes + jitter.
    assert retry_delay_seconds(50) <= 305


# Every upload type the API accepts has exactly one parser.
def test_every_supported_upload_type_has_exactly_one_parser() -> None:
    # The map's extensions match the accepted upload types.
    assert sorted(build_parsers_by_extension()) == [".csv", ".docx", ".md", ".pdf", ".txt", ".xlsx"]

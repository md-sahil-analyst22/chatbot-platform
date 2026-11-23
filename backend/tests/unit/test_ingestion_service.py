# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The ingestion use case (P2.2 - P2.8) with in-memory fakes: happy path,
#                'unchanged file = zero new chunks' (Phase 2 exit criterion), duplicate and
#                crashed jobs, deletion mid-run, provider retries, safe failure messages and
#                chunking changes mid-run.
# How to run: cd backend && uv run pytest tests/unit/test_ingestion_service.py (no database).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""IngestionService."""

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.knowledge — in-memory stand-ins for the Phase 2 ports.
from tests.fakes.knowledge import (
    FakeCrawler,
    FakeParser,
    FakePolicySource,
    FakeUnitOfWork,
    InMemoryChunkRepository,
    InMemorySourceRepository,
    RecordingQueue,
)

# From tests.fakes.providers — vendor fakes: FakeEmbedder = deterministic vectors;
#   InMemoryObjectStore = files in a dict.
from tests.fakes.providers import FakeEmbedder, InMemoryObjectStore

# From saathi.modules.knowledge.application.ingestion — the use case, its outcomes and the safe
#   messages it stores on a source.
from saathi.modules.knowledge.application.ingestion import (
    MSG_MISSING,
    MSG_NO_TEXT,
    MSG_PROVIDER,
    MSG_PROVIDER_REJECTED,
    MSG_RETRYING,
    MSG_TOO_LARGE,
    MSG_UNREADABLE,
    IngestionService,
    IngestOutcome,
)

# From saathi.modules.knowledge.domain.chunking — chunk rules: ChunkingPolicy.
from saathi.modules.knowledge.domain.chunking import ChunkingPolicy

# From saathi.modules.knowledge.domain.crawl — crawl settings: CrawlOptions.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.domain.entities — sources: Source; SourceStatus.
from saathi.modules.knowledge.domain.entities import Source, SourceStatus

# From saathi.platform.errors — our error types: ProviderError = a vendor failed;
#   ValidationError = invalid/unsafe input.
from saathi.platform.errors import ProviderError, ValidationError

# The test tenant and bot.
TENANT, BOT = uuid4(), uuid4()
# Where the test file is stored (tenant-prefixed, like production).
KEY = f"t/{TENANT}/bots/{BOT}/files/fees.txt"


# Fakes wired into a real IngestionService.
class Harness:
    """Everything a test may look at or change."""

    # Build it; a test may pass its own parser or a failing embedder.
    def __init__(self, *, parser: FakeParser | None = None, embedder_mode: str = "ok") -> None:
        # Source storage.
        self.sources = InMemorySourceRepository()
        # Chunk storage (keeps chunk counts in the source fake).
        self.chunks = InMemoryChunkRepository(self.sources)
        # The bot's chunk settings (changeable by tests).
        self.policies = FakePolicySource()
        # File storage.
        self.store = InMemoryObjectStore()
        # Records follow-up jobs.
        self.queue = RecordingQueue()
        # The parser for '.txt'.
        self.parser = parser or FakeParser()
        # The website crawler.
        self.crawler = FakeCrawler()
        # The embedder ('ok', 'error' or 'timeout').
        self.embedder = FakeEmbedder(embedder_mode)  # type: ignore[arg-type]  # test modes
        # The real use case with the fakes plugged in.
        self.service = IngestionService(
            uow=FakeUnitOfWork(self.sources, self.chunks, self.policies),
            store=self.store,
            parsers={".txt": self.parser},
            crawler=self.crawler,
            embedder=self.embedder,
            queue=self.queue,
            max_chunks=50,
        )

    # Store a file and a queued source pointing at it; return the source id.
    async def add_file(self, data: bytes = b"file v1") -> UUID:
        # Save the bytes.
        await self.store.put(KEY, data, "text/plain")
        # A queued source for them.
        source = Source(
            id=uuid4(), tenant_id=TENANT, bot_id=BOT, kind="file", uri=KEY, title="fees.txt"
        )
        # Save it.
        await self.sources.add(source)
        # Its id.
        return source.id

    # Load a source (it must exist).
    async def status(self, source_id: UUID) -> Source:
        # Look it up.
        found = await self.sources.get(TENANT, source_id)
        # It must be there.
        assert found is not None
        # Return it.
        return found

    # Put a finished source back in the queue (like the Re-sync button).
    async def requeue(self, source_id: UUID) -> None:
        # Load it.
        s = await self.status(source_id)
        # ready/failed -> queued.
        s.requeue()
        # Save it.
        await self.sources.save(s)


# Normal run: chunks stored, source ready, passages embedded as documents.
async def test_happy_path_stores_chunks_and_marks_ready() -> None:
    # Fakes + service.
    h = Harness()
    # A queued file.
    sid = await h.add_file()
    # Process it: done.
    assert await h.service.ingest(TENANT, sid) is IngestOutcome.DONE
    # Reload it.
    s = await h.status(sid)
    # Ready, with a fingerprint and no error.
    assert s.status is SourceStatus.READY and s.content_hash and s.error is None
    # One chunk was stored.
    assert await h.chunks.count_for_source(TENANT, sid) == 1
    # Passages were embedded as documents (Gemini's document prefix).
    assert h.embedder.last_task == "document"


# Phase 2 exit criterion: re-ingesting an unchanged file creates zero new chunks.
async def test_reingesting_an_unchanged_file_creates_zero_new_chunks() -> None:
    # Fakes + service.
    h = Harness()
    # A queued file...
    sid = await h.add_file()
    # ...processed once.
    await h.service.ingest(TENANT, sid)
    # How many chunks were inserted so far.
    inserted_before = h.chunks.inserted
    # Queue it again (same bytes, same settings).
    await h.requeue(sid)
    # Second run: unchanged.
    assert await h.service.ingest(TENANT, sid) is IngestOutcome.UNCHANGED
    # Not a single new chunk.
    assert h.chunks.inserted == inserted_before
    # Still ready.
    assert (await h.status(sid)).status is SourceStatus.READY


# Changed content replaces the old chunks.
async def test_changed_content_replaces_chunks() -> None:
    # Fakes + service.
    h = Harness()
    # Version 1 of the file...
    sid = await h.add_file(b"v1")
    # ...processed.
    await h.service.ingest(TENANT, sid)
    # New bytes...
    await h.store.put(KEY, b"v2", "text/plain")
    # ...that parse to new text.
    h.parser.pages = ["# Fees\n\nGST filing now costs 600 rupees.", "# Hours\n\nOpen 10 to 7."]
    # Queue it again.
    await h.requeue(sid)
    # Processed: done.
    assert await h.service.ingest(TENANT, sid) is IngestOutcome.DONE
    # The source's chunk texts now.
    texts = [r.chunk.text for r in h.chunks.rows if r.source_id == sid]
    # The new price is there and the old one is gone.
    assert any("600" in t for t in texts) and not any("500" in t for t in texts)


# Same bytes but new chunk settings: the chunks are rebuilt.
async def test_chunking_policy_change_alone_triggers_reprocessing() -> None:
    # Fakes + service.
    h = Harness()
    # A file...
    sid = await h.add_file()
    # ...processed with the default settings.
    await h.service.ingest(TENANT, sid)
    # The bot publishes new chunk settings.
    h.policies.policy = ChunkingPolicy(500, 0.1)
    # Queue it again.
    await h.requeue(sid)
    # The fingerprint differs, so it is processed again.
    assert await h.service.ingest(TENANT, sid) is IngestOutcome.DONE


# A duplicate job does nothing, but ARQ's retry takes over a crashed run.
async def test_duplicate_job_is_skipped_but_a_retry_takes_over_a_crashed_run() -> None:
    # Fakes + service.
    h = Harness()
    # A file.
    sid = await h.add_file()
    # Simulate a run that crashed after claiming: status stuck at processing.
    s = await h.status(sid)
    # queued -> processing.
    s.start_processing()
    # Save it.
    await h.sources.save(s)
    # A duplicate first-attempt job leaves it alone...
    assert await h.service.ingest(TENANT, sid, attempt=1) is IngestOutcome.SKIPPED
    # ...but a retry (attempt 2) finishes the crashed run.
    assert await h.service.ingest(TENANT, sid, attempt=2) is IngestOutcome.DONE


# A source that no longer exists: nothing to do.
async def test_deleted_source_is_gone() -> None:
    # Fakes + service.
    h = Harness()
    # An unknown id is 'gone'.
    assert await h.service.ingest(TENANT, uuid4()) is IngestOutcome.GONE


# 🔒 A job with the wrong tenant can't see or touch the source.
async def test_another_tenants_source_is_invisible() -> None:
    # Fakes + service.
    h = Harness()
    # Tenant A's file.
    sid = await h.add_file()
    # A job naming another tenant treats it as missing.
    assert await h.service.ingest(uuid4(), sid) is IngestOutcome.GONE
    # The real source is untouched.
    assert (await h.status(sid)).status is SourceStatus.QUEUED


# Provider failures are retried, then fail with a safe message.
async def test_provider_failure_retries_then_fails_with_a_safe_message() -> None:
    # An embedder that always fails.
    h = Harness(embedder_mode="error")
    # A file.
    sid = await h.add_file()
    # Attempt 1 of 3: retry.
    assert await h.service.ingest(TENANT, sid, attempt=1, max_attempts=3) is IngestOutcome.RETRY
    # Reload.
    s = await h.status(sid)
    # Back in the queue with the 'retrying' message.
    assert s.status is SourceStatus.QUEUED and s.error == MSG_RETRYING
    # The last attempt fails for good.
    assert await h.service.ingest(TENANT, sid, attempt=3, max_attempts=3) is IngestOutcome.FAILED
    # Reload.
    s = await h.status(sid)
    # Failed with a safe message (no vendor detail).
    assert s.status is SourceStatus.FAILED and s.error == MSG_PROVIDER


# Timeouts are retried like other provider errors.
async def test_provider_timeout_is_also_retried() -> None:
    # An embedder that always times out.
    h = Harness(embedder_mode="timeout")
    # A file.
    sid = await h.add_file()
    # First of two attempts: retry.
    assert await h.service.ingest(TENANT, sid, attempt=1, max_attempts=2) is IngestOutcome.RETRY


# Each case: a parser that makes the file unusable, and the safe message we expect.
@pytest.mark.parametrize(
    ("parser", "message"),
    [
        # The parser crashes with an internal message.
        (FakeParser(error=RuntimeError("corrupt xref table at 0x1234")), MSG_UNREADABLE),
        # The file has no text.
        (FakeParser(pages=["   "]), MSG_NO_TEXT),
        # The file would make far more than 50 chunks.
        (FakeParser(pages=[("word " * 300 + "\n\n") * 200]), MSG_TOO_LARGE),
    ],
)
# Unusable files fail with our safe message, never the parser's internal one.
async def test_unusable_files_fail_with_safe_messages(parser: FakeParser, message: str) -> None:
    # Fakes with that parser.
    h = Harness(parser=parser)
    # A file.
    sid = await h.add_file()
    # Processed: failed.
    assert await h.service.ingest(TENANT, sid) is IngestOutcome.FAILED
    # Reload.
    s = await h.status(sid)
    # Failed with our message (R17/R29).
    assert s.status is SourceStatus.FAILED and s.error == message
    # The parser's internal detail never leaks.
    assert "xref" not in (s.error or "")


# A stored file that disappeared fails with a safe message.
async def test_missing_stored_file_fails_with_a_safe_message() -> None:
    # Fakes + service.
    h = Harness()
    # A file...
    sid = await h.add_file()
    # ...whose bytes were removed from storage.
    await h.store.delete(KEY)
    # Processed: failed.
    assert await h.service.ingest(TENANT, sid) is IngestOutcome.FAILED
    # With the 'upload it again' message.
    assert (await h.status(sid)).error == MSG_MISSING


# New chunk settings published DURING a run: the source is queued again afterwards.
async def test_chunking_change_during_a_run_requeues_the_source() -> None:
    # Fakes + service.
    h = Harness()
    # A file.
    sid = await h.add_file()
    # The real fake embed method.
    original_embed = h.embedder.embed

    # An embed that 'publishes' new settings while the run is in progress.
    async def embed_then_publish(texts, *, task):  # type: ignore[no-untyped-def]
        # The bot's settings change mid-run.
        h.policies.policy = ChunkingPolicy(500, 0.1)
        # Then embed as usual.
        return await original_embed(texts, task=task)

    # Swap it in.
    h.embedder.embed = embed_then_publish  # type: ignore[method-assign]
    # The run finishes, then notices the change: requeued.
    assert await h.service.ingest(TENANT, sid) is IngestOutcome.REQUEUED
    # Back in the queue...
    assert (await h.status(sid)).status is SourceStatus.QUEUED
    # ...with a follow-up job sent.
    assert h.queue.jobs == [(TENANT, sid)]


# Website sources go through the crawler and keep the page address.
async def test_website_source_uses_the_crawler() -> None:
    # Fakes + service.
    h = Harness()
    # A queued website source.
    source = Source(
        id=uuid4(),
        tenant_id=TENANT,
        bot_id=BOT,
        kind="url",
        uri="https://ex.com/",
        crawl=CrawlOptions("https://ex.com/"),
    )
    # Save it.
    await h.sources.add(source)
    # Processed: done.
    assert await h.service.ingest(TENANT, source.id) is IngestOutcome.DONE
    # The chunk remembers which page it came from.
    assert h.chunks.rows[0].chunk.url == "https://ex.com/"


# 🔒 An unsafe website fails at once (retrying can't make it safe).
async def test_unsafe_website_fails_without_retry() -> None:
    # Fakes + service.
    h = Harness()
    # The crawler refuses the address as unsafe.
    h.crawler.error = ValidationError("URL points to a private or reserved network address")
    # A queued website source.
    source = Source(
        id=uuid4(),
        tenant_id=TENANT,
        bot_id=BOT,
        kind="url",
        uri="https://ex.com/",
        crawl=CrawlOptions("https://ex.com/"),
    )
    # Save it.
    await h.sources.add(source)
    # Failed on the first attempt even though 5 are allowed.
    assert await h.service.ingest(TENANT, source.id, max_attempts=5) is IngestOutcome.FAILED


# An unreachable website is retried later.
async def test_unreachable_website_is_retried() -> None:
    # Fakes + service.
    h = Harness()
    # The crawler can't reach the site.
    h.crawler.error = ProviderError("the website could not be reached")
    # A queued website source.
    source = Source(
        id=uuid4(),
        tenant_id=TENANT,
        bot_id=BOT,
        kind="url",
        uri="https://ex.com/",
        crawl=CrawlOptions("https://ex.com/"),
    )
    # Save it.
    await h.sources.add(source)
    # First of two attempts: retry.
    assert await h.service.ingest(TENANT, source.id, max_attempts=2) is IngestOutcome.RETRY


# A permanent refusal (e.g. 403 unpaid billing) fails at once: retrying can't help.
async def test_provider_rejection_fails_at_once_without_retry() -> None:
    # An embedder that is refused for good.
    h = Harness(embedder_mode="rejected")
    # A file.
    sid = await h.add_file()
    # First of five attempts: failed, not retry.
    assert await h.service.ingest(TENANT, sid, attempt=1, max_attempts=5) is IngestOutcome.FAILED
    # Reload.
    s = await h.status(sid)
    # Failed with the 'account or configuration problem' message.
    assert s.status is SourceStatus.FAILED and s.error == MSG_PROVIDER_REJECTED

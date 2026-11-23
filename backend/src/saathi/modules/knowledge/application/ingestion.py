# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The 'learn a document' process, run by the background worker (P2.2 - P2.8).
# Steps for one source:
#   1. CLAIM   (short transaction) lock the source row; queued -> processing; read the bot's
#              chunking settings. A duplicate job finds it already taken and stops.
#   2. FETCH   (no transaction) file bytes from storage, or crawl the website.
#   3. FINGERPRINT  sha256 of (content + chunking settings + embedding model). Same as last
#              time? -> mark ready, touch no chunks (re-upload of an unchanged file = 0 new
#              chunks, P2.8).
#   4. PARSE -> CLEAN -> CHUNK -> EMBED  (no transaction; parsing runs in a thread, R32).
#   5. SAVE    (one transaction, R26) delete the old chunks, insert the new ones, mark ready.
#              If the bot's chunking settings changed while we worked, queue it again.
#   6. FAILURE  a safe, human message is stored on the source (never a stack trace, R17/R29).
#              Provider hiccups (timeouts, 429/5xx) ask the worker to retry later, a bounded
#              number of times (R33). A permanent refusal (e.g. 401/403) fails at once.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Ingestion use case (P2.2 - P2.8). Orchestrates ports; contains no vendor code."""

# asyncio — runs CPU-heavy parsing in a thread so the worker's event loop stays free (R32).
import asyncio

# hashlib — fingerprints (hashes) such as SHA-256.
import hashlib

# From collections.abc — standard type names: Mapping = read-only dict type.
from collections.abc import Mapping

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# structlog — structured logging (JSON log lines).
import structlog

# From saathi.modules.knowledge.application.chunker — chunking: chunk_pages = text -> chunks.
from saathi.modules.knowledge.application.chunker import chunk_pages

# From saathi.modules.knowledge.application.cleaner — cleaning: TextPage = one page of text;
#   clean_pages = tidy pages.
from saathi.modules.knowledge.application.cleaner import TextPage, clean_pages

# From saathi.modules.knowledge.domain.chunking — chunk rules: Chunk = one passage;
#   ChunkingPolicy = size + overlap.
from saathi.modules.knowledge.domain.chunking import Chunk, ChunkingPolicy

# From saathi.modules.knowledge.domain.entities — sources: Source = one document/site;
#   SourceKind = file or url; SourceStatus = its life-cycle states.
from saathi.modules.knowledge.domain.entities import Source, SourceKind, SourceStatus

# From saathi.modules.knowledge.ports.external — outside needs: IngestQueue = put a job on the
#   queue.
from saathi.modules.knowledge.ports.external import IngestQueue

# From saathi.modules.knowledge.ports.providers — vendor contracts: DocumentParser = file ->
#   text; Embedder = text -> vectors; WebCrawler = website -> pages.
from saathi.modules.knowledge.ports.providers import DocumentParser, Embedder, WebCrawler

# From saathi.modules.knowledge.ports.unit_of_work — transactions: IngestionUnitOfWork = open a
#   tenant-bound transaction.
from saathi.modules.knowledge.ports.unit_of_work import IngestionUnitOfWork

# From saathi.platform.errors — our error types: NotFoundError = 404; ProviderError = a vendor
#   failed (maybe temporarily); ProviderRejectedError = the vendor refused for good;
#   ValidationError = invalid input (our own, safe message).
from saathi.platform.errors import (
    NotFoundError,
    ProviderError,
    ProviderRejectedError,
    ValidationError,
)

# From saathi.platform.storage — file storage contract: ObjectStore = save/read files.
from saathi.platform.storage import ObjectStore

# The logger for this file.
log = structlog.get_logger()

# 🔒 Cost and time bound: a source may produce at most 3,000 chunks (~2M tokens to embed).
MAX_CHUNKS_PER_SOURCE = 3000

# Safe messages shown to the tenant (no internals, R29).
MSG_UNREADABLE = "We could not read this file. Please check it opens correctly and upload again."
MSG_NO_TEXT = "No readable text was found. If this is a scanned PDF, upload a text version."
MSG_MISSING = "The uploaded file is missing. Please upload it again."
MSG_TOO_LARGE = "This source is too large to process. Please split it into smaller files."
MSG_PROVIDER = "The AI service was unavailable. Please use 'Re-sync' to try again later."
MSG_RETRYING = "The AI service was busy. Retrying automatically."
MSG_PROVIDER_REJECTED = (
    "The AI service refused the request (account or configuration problem). "
    "Please contact support; use 'Re-sync' once it is fixed."
)
MSG_CRAWL = "We could not fetch any page from this website."


# What happened to one job (logged, and used by the worker to decide on retries).
class IngestOutcome(StrEnum):
    # Chunks replaced, source ready.
    DONE = "done"
    # Same fingerprint as last time: ready, no chunk changes.
    UNCHANGED = "unchanged"
    # Another job has it, or it isn't queued any more: nothing done.
    SKIPPED = "skipped"
    # The source (or its bot) was deleted meanwhile: nothing done.
    GONE = "gone"
    # Failed for good; the reason is stored on the source.
    FAILED = "failed"
    # Temporary provider problem: source queued again, the worker should retry later.
    RETRY = "retry"
    # Done, but the bot's chunking settings changed meanwhile: queued again with the new ones.
    REQUEUED = "requeued"


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# What we fetched and cleaned for one source.
class _Content:
    # Clean pages ready for chunking.
    pages: list[TextPage]
    # sha256 of the raw content (before settings are mixed in).
    raw_hash: str


# The fingerprint that decides 'unchanged': content + chunking settings + embedding model.
def ingest_fingerprint(raw_hash: str, policy: ChunkingPolicy, model_name: str) -> str:
    """Changes when the file, the bot's chunking settings or the embedding model change."""
    # Mix the three into one sha256 (64 hex characters, fits sources.content_hash).
    return hashlib.sha256(f"{raw_hash}|{policy.signature}|{model_name}".encode()).hexdigest()


# The extension of a storage key ('t/.../files/price_list.pdf' -> '.pdf').
def _extension(key: str) -> str:
    # The part after the last dot of the last path segment.
    name = key.rsplit("/", 1)[-1]
    # '.pdf' or ''.
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


# The use case.
class IngestionService:
    """Processes one source end to end. Safe to run twice for the same source (R33)."""

    # Receive every collaborator through the constructor (R21).
    def __init__(
        self,
        *,
        uow: IngestionUnitOfWork,
        store: ObjectStore,
        parsers: Mapping[str, DocumentParser],
        crawler: WebCrawler,
        embedder: Embedder,
        queue: IngestQueue,
        max_chunks: int = MAX_CHUNKS_PER_SOURCE,
    ) -> None:
        # Opens tenant-bound transactions.
        self._uow = uow
        # Private document storage.
        self._store = store
        # Extension -> parser ('.pdf' -> PDF parser).
        self._parsers = parsers
        # Website crawler.
        self._crawler = crawler
        # Embedding provider.
        self._embedder = embedder
        # Used to queue the source again when chunking settings changed meanwhile.
        self._queue = queue
        # Upper bound of chunks per source.
        self._max_chunks = max_chunks

    # Process one source. `attempt` starts at 1; `max_attempts` bounds automatic retries.
    async def ingest(
        self, tenant_id: UUID, source_id: UUID, *, attempt: int = 1, max_attempts: int = 1
    ) -> IngestOutcome:
        """Run the steps above; never raises for problems with the source itself."""
        # Step 1: claim.
        claimed = await self._claim(tenant_id, source_id, attempt)
        # Not ours to process.
        if isinstance(claimed, IngestOutcome):
            # Report why.
            return claimed
        # The claimed source and the settings to use.
        source, policy = claimed
        # Steps 2-5, with failures turned into a safe stored reason.
        try:
            # Do the work.
            return await self._process(source, policy)
        # Our own validation messages are safe to show (unsafe URL, no text, too big...).
        except ValidationError as exc:
            # Store the message; no retry (it would fail the same way).
            return await self._fail(source, exc.message or MSG_UNREADABLE, retry=False)
        # The stored file is gone.
        except NotFoundError:
            # Store a safe message.
            return await self._fail(source, MSG_MISSING, retry=False)
        # A vendor refused for good (bad key, unpaid billing, bad request): no retry.
        except ProviderRejectedError as exc:
            # Error level: an operator must fix the account or configuration (type only logged).
            log.error("ingest.provider_rejected", error_type=type(exc).__name__, attempt=attempt)
            # Store a safe message; retrying can't help.
            return await self._fail(source, MSG_PROVIDER_REJECTED, retry=False)
        # A vendor (embedding/crawl) failed temporarily: retry while attempts remain.
        except ProviderError as exc:
            # Log the type only (messages could contain vendor detail).
            log.warning("ingest.provider_error", error_type=type(exc).__name__, attempt=attempt)
            # Retry if this wasn't the last attempt.
            retry = attempt < max_attempts
            # Store the right message.
            return await self._fail(source, MSG_RETRYING if retry else MSG_PROVIDER, retry=retry)

    # Step 1: lock the row, queued -> processing, read chunking settings.
    async def _claim(
        self, tenant_id: UUID, source_id: UUID, attempt: int
    ) -> tuple[Source, ChunkingPolicy] | IngestOutcome:
        # One short transaction.
        async with self._uow(tenant_id) as repos:
            # Lock the row so a duplicate job waits here, then sees our status change.
            source = await repos.sources.get_for_update(tenant_id, source_id)
            # Deleted meanwhile (or never existed).
            if source is None:
                # Nothing to do.
                return IngestOutcome.GONE
            # Normal case: it's waiting for us.
            if source.status is SourceStatus.QUEUED:
                # queued -> processing (the domain checks the move).
                source.start_processing()
                # Save the new status.
                await repos.sources.save(source)
            # A retry of a run that crashed half-way (worker restart): take it over.
            elif not (source.status is SourceStatus.PROCESSING and attempt > 1):
                # Anything else: another job has it or it's finished. Duplicate job: stop.
                return IngestOutcome.SKIPPED
            # The bot's chunking settings, read now so the whole run uses one version.
            policy = await repos.policies.policy_for(tenant_id, source.bot_id)
        # Claimed (the block's end committed the status change).
        return source, policy

    # Steps 2-5.
    async def _process(self, source: Source, policy: ChunkingPolicy) -> IngestOutcome:
        # Step 2: fetch and clean.
        content = await self._fetch(source)
        # Step 3: fingerprint.
        fingerprint = ingest_fingerprint(content.raw_hash, policy, self._embedder.model_name)
        # Same as the last successful run: nothing to redo.
        if source.is_unchanged(fingerprint):
            # Mark ready without touching chunks.
            return await self._save(source, policy, fingerprint, chunks=None, vectors=None)
        # Step 4: chunk.
        chunks = chunk_pages(content.pages, policy)
        # Nothing usable.
        if not chunks:
            # Safe message, no retry.
            raise ValidationError(MSG_NO_TEXT)
        # Bounded cost/time.
        if len(chunks) > self._max_chunks:
            # Safe message, no retry.
            raise ValidationError(MSG_TOO_LARGE)
        # Step 4b: embed (the adapter batches the calls).
        vectors = await self._embedder.embed([c.text for c in chunks], task="document")
        # Step 5: save in one transaction.
        return await self._save(source, policy, fingerprint, chunks=chunks, vectors=vectors)

    # Step 2: get the source's text as clean pages.
    async def _fetch(self, source: Source) -> _Content:
        # Uploaded files.
        if source.kind == SourceKind.FILE:
            # Pick the parser by the stored file's extension (validated at upload).
            parser = self._parsers.get(_extension(source.uri))
            # No parser for it (shouldn't happen: upload checks the type).
            if parser is None:
                # Safe message.
                raise ValidationError(MSG_UNREADABLE)
            # Read the bytes (NotFoundError if missing).
            data = await self._store.get(source.uri)
            # Parse in a worker thread: PDF parsing is CPU-heavy (R32).
            try:
                # The parsed document.
                doc = await asyncio.to_thread(parser.parse, data, source.title or source.uri)
            # Parsers raise all kinds of errors on broken files; none of their detail is shown.
            except Exception as exc:  # any parser failure = unreadable file
                # Log the type only.
                log.warning("ingest.parse_failed", error_type=type(exc).__name__)
                # Safe message.
                raise ValidationError(MSG_UNREADABLE) from None
            # Pages for the cleaner.
            pages = [TextPage(p.text, page=p.number, title=source.title or "") for p in doc.pages]
            # Raw fingerprint = the file's bytes.
            raw_hash = hashlib.sha256(data).hexdigest()
        # Websites.
        else:
            # The crawl settings (always present for website sources: the domain enforces it).
            assert source.crawl is not None  # noqa: S101 - domain invariant, not input checking
            # Crawl (raises ValidationError for unsafe URLs, ProviderError if nothing worked).
            crawled = await self._crawler.crawl(source.crawl)
            # Nothing came back.
            if not crawled:
                # Safe message.
                raise ValidationError(MSG_CRAWL)
            # Pages for the cleaner, in address order so the fingerprint is stable.
            crawled = sorted(crawled, key=lambda p: p.url)
            # One TextPage per web page.
            pages = [TextPage(p.text, url=p.url, title=p.title) for p in crawled]
            # Raw fingerprint = every page's address and text.
            raw_hash = hashlib.sha256(
                "\n".join(f"{p.url}\n{p.text}" for p in crawled).encode("utf-8")
            ).hexdigest()
        # Clean them (P2.5).
        return _Content(pages=clean_pages(pages), raw_hash=raw_hash)

    # Step 5: one transaction that replaces chunks and marks the source ready.
    async def _save(
        self,
        source: Source,
        policy: ChunkingPolicy,
        fingerprint: str,
        *,
        chunks: list[Chunk] | None,
        vectors: list[list[float]] | None,
    ) -> IngestOutcome:
        # Whether to queue it again after the commit.
        requeue = False
        # One transaction (R26).
        async with self._uow(source.tenant_id) as repos:
            # Lock and reload: it may have been deleted or changed while we worked.
            current = await repos.sources.get_for_update(source.tenant_id, source.id)
            # Deleted meanwhile: stop (its chunks went with it).
            if current is None:
                # Nothing saved.
                return IngestOutcome.GONE
            # Someone else moved it on (shouldn't happen while we hold 'processing').
            if current.status is not SourceStatus.PROCESSING:
                # Nothing saved.
                return IngestOutcome.SKIPPED
            # New content: swap the chunks.
            if chunks is not None and vectors is not None:
                # Delete old + insert new, in this same transaction.
                await repos.chunks.replace_for_source(current, chunks, vectors)
            # processing -> ready, remembering the fingerprint.
            current.mark_ready(fingerprint)
            # Did the bot's chunking settings change while we worked (e.g. a publish)?
            if await repos.policies.policy_for(current.tenant_id, current.bot_id) != policy:
                # ready -> queued: it must be redone with the new settings.
                current.requeue()
                # Queue it after the commit.
                requeue = True
            # Save the status.
            await repos.sources.save(current)
        # After the commit: queue the follow-up job.
        if requeue:
            # Queue it.
            await self._queue.enqueue_ingest(source.tenant_id, source.id)
            # Report it.
            return IngestOutcome.REQUEUED
        # Report what happened.
        return IngestOutcome.UNCHANGED if chunks is None else IngestOutcome.DONE

    # Store a safe failure reason; for retries, put the source back in the queue.
    async def _fail(self, source: Source, reason: str, *, retry: bool) -> IngestOutcome:
        # One short transaction.
        async with self._uow(source.tenant_id) as repos:
            # Lock and reload.
            current = await repos.sources.get_for_update(source.tenant_id, source.id)
            # Deleted meanwhile.
            if current is None:
                # Nothing to record.
                return IngestOutcome.GONE
            # Only a source we are processing can fail.
            if current.status is not SourceStatus.PROCESSING:
                # Nothing to record.
                return IngestOutcome.SKIPPED
            # processing -> failed, with the reason.
            current.mark_failed(reason)
            # A retry puts it back in the queue (failed -> queued) so the next attempt claims it.
            if retry:
                # Back to queued.
                current.requeue()
            # Save.
            await repos.sources.save(current)
        # The worker turns RETRY into a delayed retry of the same job.
        return IngestOutcome.RETRY if retry else IngestOutcome.FAILED

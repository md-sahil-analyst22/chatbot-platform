# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: In-memory stand-ins for the knowledge and conversation ports added in Phase 2, so use
#       cases can be tested in milliseconds without Postgres, Redis or vendors.
# Rule: each repository fake passes the same contract suite as its SQL adapter (R35), so a test
#       that passes on the fake means the same on the real thing.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Phase 2 fakes: repositories, unit of work, queue, parser, crawler, retriever, logs."""

# math — cosine similarity for the fake vector search.
import math

# From collections.abc — standard type names: AsyncIterator, Awaitable, Callable, Sequence.
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

# From contextlib — context-manager helpers: asynccontextmanager.
from contextlib import asynccontextmanager

# From dataclasses — quick data classes: dataclass, field.
from dataclasses import dataclass, field

# From datetime — dates and times: UTC, datetime.
from datetime import UTC, datetime

# From uuid — unique ids: UUID, uuid4.
from uuid import UUID, uuid4

# From saathi.modules.conversation.ports.retrieval — conversation's retrieval types: Retrieval =
#   what was found; RetrievalRequest = the search knobs.
from saathi.modules.conversation.ports.retrieval import Retrieval, RetrievalRequest

# From saathi.modules.conversation.ports.unanswered — UnansweredQuestion = one record.
from saathi.modules.conversation.ports.unanswered import UnansweredQuestion

# From saathi.modules.knowledge.domain.chunking — Chunk = one passage; ChunkingPolicy.
from saathi.modules.knowledge.domain.chunking import Chunk, ChunkingPolicy

# From saathi.modules.knowledge.domain.crawl — CrawlOptions = one crawl's settings.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.domain.entities — Source; SourceStatus.
from saathi.modules.knowledge.domain.entities import Source, SourceStatus

# From saathi.modules.knowledge.domain.faq — Faq = one question + exact answer.
from saathi.modules.knowledge.domain.faq import Faq

# From saathi.modules.knowledge.ports.providers — data shapes: CrawledPage = one crawled page;
#   ParsedDocument / ParsedPage = a parsed file and one of its pages.
from saathi.modules.knowledge.ports.providers import CrawledPage, ParsedDocument, ParsedPage

# From saathi.modules.knowledge.ports.repositories — ChunkHit = one search hit; FaqMatch = the
#   closest FAQ; SourceListing = a source + counts and times.
from saathi.modules.knowledge.ports.repositories import ChunkHit, FaqMatch, SourceListing

# From saathi.modules.knowledge.ports.unit_of_work — IngestionRepositories = the repositories in
#   one transaction.
from saathi.modules.knowledge.ports.unit_of_work import IngestionRepositories

# From saathi.platform.errors — ConflictError = 409; NotFoundError = 404.
from saathi.platform.errors import ConflictError, NotFoundError


# Copy a Source (the fake 'database' stores copies, like a real one stores rows).
def _copy(s: Source) -> Source:
    # Same fields, new object.
    return Source(
        id=s.id,
        tenant_id=s.tenant_id,
        bot_id=s.bot_id,
        kind=s.kind,
        uri=s.uri,
        content_hash=s.content_hash,
        status=s.status,
        title=s.title,
        error=s.error,
        crawl=s.crawl,
    )


# Fake SourceRepository.
class InMemorySourceRepository:
    # Empty store; `bots` = (tenant, bot) pairs that exist (for the foreign-key rule).
    def __init__(self, bots: set[tuple[UUID, UUID]] | None = None) -> None:
        # id -> stored copy.
        self.rows: dict[UUID, Source] = {}
        # id -> created time.
        self.created: dict[UUID, datetime] = {}
        # id -> synced time.
        self.synced: dict[UUID, datetime | None] = {}
        # Existing bots (None = any bot exists).
        self.bots = bots
        # Chunk counts per source (set by the chunk fake when shared).
        self.chunk_counts: dict[UUID, int] = {}

    # Save a new source.
    async def add(self, source: Source) -> None:
        # The bot must exist for the tenant (mirrors the composite foreign key).
        if self.bots is not None and (source.tenant_id, source.bot_id) not in self.bots:
            # 404.
            raise NotFoundError("bot not found")
        # Same uri for the same bot -> conflict (mirrors the unique constraint).
        if any(
            (r.tenant_id, r.bot_id, r.uri) == (source.tenant_id, source.bot_id, source.uri)
            for r in self.rows.values()
        ):
            # 409.
            raise ConflictError("this source already exists for the bot")
        # Store a copy.
        self.rows[source.id] = _copy(source)
        # Record the time.
        self.created[source.id] = datetime.now(UTC)
        # Not synced yet.
        self.synced[source.id] = None

    # Load one.
    async def get(self, tenant_id: UUID, source_id: UUID) -> Source | None:
        # Tenant filter.
        row = self.rows.get(source_id)
        # Copy or None.
        return _copy(row) if row is not None and row.tenant_id == tenant_id else None

    # Load by uri.
    async def get_by_uri(self, tenant_id: UUID, bot_id: UUID, uri: str) -> Source | None:
        # Linear scan.
        for row in self.rows.values():
            # Match all three.
            if (row.tenant_id, row.bot_id, row.uri) == (tenant_id, bot_id, uri):
                # Copy.
                return _copy(row)
        # None.
        return None

    # Load with lock (no locking needed in memory).
    async def get_for_update(self, tenant_id: UUID, source_id: UUID) -> Source | None:
        # Same as get.
        return await self.get(tenant_id, source_id)

    # Save changes.
    async def save(self, source: Source) -> None:
        # Must exist for this tenant.
        row = self.rows.get(source.id)
        # Gone -> 404.
        if row is None or row.tenant_id != source.tenant_id:
            # 404.
            raise NotFoundError("source not found")
        # Store a copy.
        self.rows[source.id] = _copy(source)
        # Ready -> synced now.
        if source.status is SourceStatus.READY:
            # Record the time.
            self.synced[source.id] = datetime.now(UTC)

    # Delete.
    async def delete(self, tenant_id: UUID, source_id: UUID) -> bool:
        # Tenant filter.
        row = self.rows.get(source_id)
        # Not ours.
        if row is None or row.tenant_id != tenant_id:
            # Nothing deleted.
            return False
        # Remove it.
        del self.rows[source_id]
        # Deleted.
        return True

    # List newest first.
    async def list_for_bot(self, tenant_id: UUID, bot_id: UUID, limit: int) -> list[SourceListing]:
        # The bot's rows.
        rows = [r for r in self.rows.values() if (r.tenant_id, r.bot_id) == (tenant_id, bot_id)]
        # Newest first.
        rows.sort(key=lambda r: self.created[r.id], reverse=True)
        # As listings.
        return [
            SourceListing(
                source=_copy(r),
                created_at=self.created[r.id],
                synced_at=self.synced.get(r.id),
                chunk_count=self.chunk_counts.get(r.id, 0),
            )
            for r in rows[:limit]
        ]

    # All of a bot's sources.
    async def all_for_bot_for_update(self, tenant_id: UUID, bot_id: UUID) -> list[Source]:
        # Filtered copies, stable order.
        return sorted(
            (
                _copy(r)
                for r in self.rows.values()
                if (r.tenant_id, r.bot_id) == (tenant_id, bot_id)
            ),
            key=lambda s: str(s.id),
        )


# @dataclass: a stored chunk.
@dataclass
class _StoredChunk:
    # Row id.
    id: UUID
    # Tenant.
    tenant_id: UUID
    # Bot.
    bot_id: UUID
    # Source.
    source_id: UUID
    # Source title.
    title: str
    # The chunk.
    chunk: Chunk
    # Its vector.
    vector: list[float]


# Cosine similarity of two vectors.
def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    # Dot product / (norms).
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    # Norms.
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    # Zero-safe.
    return dot / (na * nb) if na and nb else 0.0


# Fake ChunkRepository (naive search, same contract).
class InMemoryChunkRepository:
    # Empty; optionally share chunk counts with a source fake.
    def __init__(self, sources: InMemorySourceRepository | None = None) -> None:
        # All stored chunks.
        self.rows: list[_StoredChunk] = []
        # Optional source fake to keep counts in.
        self._sources = sources
        # How many times chunks were inserted (to prove 'zero new chunks').
        self.inserted = 0

    # Replace a source's chunks.
    async def replace_for_source(
        self,
        source: Source,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        # Same length required.
        if len(chunks) != len(vectors):
            # Programming error.
            raise ValueError("chunks and vectors must have the same length")
        # Drop old ones.
        self.rows = [
            r
            for r in self.rows
            if not (r.tenant_id == source.tenant_id and r.source_id == source.id)
        ]
        # Add new ones.
        for c, v in zip(chunks, vectors, strict=True):
            # Store.
            self.rows.append(
                _StoredChunk(
                    uuid4(),
                    source.tenant_id,
                    source.bot_id,
                    source.id,
                    source.title or "",
                    c,
                    list(v),
                )
            )
        # Count inserts.
        self.inserted += len(chunks)
        # Keep counts in the source fake.
        if self._sources is not None:
            # Update.
            self._sources.chunk_counts[source.id] = len(chunks)

    # Count.
    async def count_for_source(self, tenant_id: UUID, source_id: UUID) -> int:
        # Filtered count.
        return sum(1 for r in self.rows if r.tenant_id == tenant_id and r.source_id == source_id)

    # Build a hit.
    @staticmethod
    def _hit(r: _StoredChunk, score: float) -> ChunkHit:
        # Same shape as SQL.
        return ChunkHit(
            chunk_id=r.id,
            source_id=r.source_id,
            source_title=r.title,
            text=r.chunk.text,
            section=r.chunk.section,
            page=r.chunk.page,
            url=r.chunk.url,
            score=score,
        )

    # Vector search.
    async def vector_search(
        self, tenant_id: UUID, bot_id: UUID, vector: Sequence[float], limit: int
    ) -> list[ChunkHit]:
        # Tenant + bot filter, then by similarity.
        rows = [r for r in self.rows if r.tenant_id == tenant_id and r.bot_id == bot_id]
        # Scored.
        scored = sorted(((r, _cosine(vector, r.vector)) for r in rows), key=lambda x: -x[1])
        # Top `limit`.
        return [self._hit(r, s) for r, s in scored[:limit]]

    # Keyword search: any shared lower-case word.
    async def keyword_search(
        self, tenant_id: UUID, bot_id: UUID, query: str, limit: int
    ) -> list[ChunkHit]:
        # Query words.
        words = set(query.lower().split())
        # Tenant + bot filter, with shared-word counts.
        scored = [
            (r, len(words & set(r.chunk.text.lower().split())))
            for r in self.rows
            if r.tenant_id == tenant_id and r.bot_id == bot_id
        ]
        # Only matches, best first.
        matches = sorted((x for x in scored if x[1] > 0), key=lambda x: -x[1])
        # Top `limit`.
        return [self._hit(r, float(n)) for r, n in matches[:limit]]


# Fake FaqRepository.
class InMemoryFaqRepository:
    # Empty; `bots` = existing (tenant, bot) pairs.
    def __init__(self, bots: set[tuple[UUID, UUID]] | None = None) -> None:
        # id -> (faq, vector).
        self.rows: dict[UUID, tuple[Faq, list[float] | None]] = {}
        # Existing bots (None = any).
        self.bots = bots

    # Add.
    async def add(self, faq: Faq, vector: Sequence[float]) -> None:
        # Bot must exist.
        if self.bots is not None and (faq.tenant_id, faq.bot_id) not in self.bots:
            # 404.
            raise NotFoundError("bot not found")
        # Store.
        self.rows[faq.id] = (faq, list(vector))

    # Update.
    async def update(self, faq: Faq, vector: Sequence[float] | None) -> None:
        # Must exist for the tenant.
        old = self.rows.get(faq.id)
        # Gone.
        if old is None or old[0].tenant_id != faq.tenant_id:
            # 404.
            raise NotFoundError("faq not found")
        # Store (keep the old vector if none given).
        self.rows[faq.id] = (faq, list(vector) if vector is not None else old[1])

    # Delete.
    async def delete(self, tenant_id: UUID, faq_id: UUID) -> bool:
        # Tenant filter.
        row = self.rows.get(faq_id)
        # Not ours.
        if row is None or row[0].tenant_id != tenant_id:
            # Nothing.
            return False
        # Remove.
        del self.rows[faq_id]
        # Done.
        return True

    # Get.
    async def get(self, tenant_id: UUID, faq_id: UUID) -> Faq | None:
        # Tenant filter.
        row = self.rows.get(faq_id)
        # FAQ or None.
        return row[0] if row is not None and row[0].tenant_id == tenant_id else None

    # List.
    async def list_for_bot(self, tenant_id: UUID, bot_id: UUID, limit: int) -> list[Faq]:
        # Filtered.
        return [f for f, _ in self.rows.values() if (f.tenant_id, f.bot_id) == (tenant_id, bot_id)][
            :limit
        ]

    # Best active match.
    async def best_match(
        self, tenant_id: UUID, bot_id: UUID, vector: Sequence[float]
    ) -> FaqMatch | None:
        # Candidates: this bot's active FAQs with a vector.
        scored = [
            (f, _cosine(vector, v))
            for f, v in self.rows.values()
            if (f.tenant_id, f.bot_id) == (tenant_id, bot_id) and f.is_active and v is not None
        ]
        # None at all.
        if not scored:
            # No match.
            return None
        # The best.
        faq, sim = max(scored, key=lambda x: x[1])
        # Match.
        return FaqMatch(faq=faq, similarity=sim)


# Fake ChunkingPolicySource with a settable policy.
class FakePolicySource:
    # Start with a policy (or the defaults).
    def __init__(self, policy: ChunkingPolicy | None = None) -> None:
        # The policy to report.
        self.policy = policy or ChunkingPolicy()

    # The bot's policy.
    async def policy_for(self, tenant_id: UUID, bot_id: UUID) -> ChunkingPolicy:
        # Always the same.
        return self.policy


# Fake unit of work over shared in-memory repositories.
class FakeUnitOfWork:
    # Share the given repositories across 'transactions'.
    def __init__(
        self,
        sources: InMemorySourceRepository,
        chunks: InMemoryChunkRepository,
        policies: FakePolicySource,
    ) -> None:
        # The bundle handed out each time.
        self.repos = IngestionRepositories(sources=sources, chunks=chunks, policies=policies)
        # How many transactions were opened.
        self.opened = 0

    # Open a 'transaction'.
    @asynccontextmanager
    async def __call__(self, tenant_id: UUID) -> AsyncIterator[IngestionRepositories]:
        # Count it.
        self.opened += 1
        # Hand out the shared repositories.
        yield self.repos


# Records queued jobs.
class RecordingQueue:
    # Empty list.
    def __init__(self) -> None:
        # (tenant, source) pairs queued.
        self.jobs: list[tuple[UUID, UUID]] = []

    # Queue one.
    async def enqueue_ingest(self, tenant_id: UUID, source_id: UUID) -> None:
        # Record it.
        self.jobs.append((tenant_id, source_id))


# Collects post-commit callbacks (like AfterCommit) so tests can run them.
class RecordingPostCommit:
    # Empty list.
    def __init__(self) -> None:
        # The callbacks.
        self.callbacks: list[Callable[[], Awaitable[None]]] = []

    # Register one.
    def add(self, callback: Callable[[], Awaitable[None]]) -> None:
        # Keep it.
        self.callbacks.append(callback)

    # Run them all ('commit').
    async def run(self) -> None:
        # In order.
        for cb in self.callbacks:
            # Run.
            await cb()


# Fake BotDirectory.
class FakeBotDirectory:
    # The (tenant, bot) pairs that exist.
    def __init__(self, bots: set[tuple[UUID, UUID]]) -> None:
        # Keep them.
        self.bots = bots

    # Does it exist?
    async def exists(self, tenant_id: UUID, bot_id: UUID) -> bool:
        # Pair lookup.
        return (tenant_id, bot_id) in self.bots


# A parser that returns fixed pages (or raises).
class FakeParser:
    # Which extensions it claims.
    supported_extensions = frozenset({".txt"})

    # Pages to return, or an exception to raise.
    def __init__(self, pages: list[str] | None = None, error: Exception | None = None) -> None:
        # Page texts.
        self.pages = pages if pages is not None else ["# Fees\n\nGST filing costs 500 rupees."]
        # Error to raise.
        self.error = error
        # How many times parse ran.
        self.calls = 0

    # Parse.
    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        # Count.
        self.calls += 1
        # Raise if asked.
        if self.error is not None:
            # Raise.
            raise self.error
        # Pages.
        return ParsedDocument(
            pages=[ParsedPage(number=i + 1, text=t) for i, t in enumerate(self.pages)]
        )


# A crawler that returns fixed pages (or raises).
class FakeCrawler:
    # Pages or an exception.
    def __init__(
        self, pages: list[CrawledPage] | None = None, error: Exception | None = None
    ) -> None:
        # Pages.
        self.pages = pages or [CrawledPage(url="https://ex.com/", title="Home", text="Hello")]
        # Error.
        self.error = error

    # Crawl.
    async def crawl(self, options: CrawlOptions) -> list[CrawledPage]:
        # Raise if asked.
        if self.error is not None:
            # Raise.
            raise self.error
        # Pages.
        return self.pages


# A retriever returning a fixed result (or raising).
@dataclass
class FakeRetriever:
    # What to return.
    result: Retrieval | None = None
    # Or what to raise.
    error: Exception | None = None
    # The requests received.
    calls: list[RetrievalRequest] = field(default_factory=list)

    # Retrieve.
    async def retrieve(
        self, tenant_id: UUID, bot_id: UUID, question: str, request: RetrievalRequest
    ) -> Retrieval:
        # Record.
        self.calls.append(request)
        # Raise if asked.
        if self.error is not None:
            # Raise.
            raise self.error
        # Result (empty by default).
        return self.result or Retrieval(faq=None, passages=[], confidence=None, reranked=False)


# Records unanswered questions.
class InMemoryUnansweredLog:
    # Empty.
    def __init__(self) -> None:
        # Records.
        self.items: list[UnansweredQuestion] = []

    # Record.
    async def record(self, item: UnansweredQuestion) -> None:
        # Keep.
        self.items.append(item)

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 Tenant isolation for the Phase 2 tables on REAL Postgres as the app role
#                (saathi_app, NOBYPASSRLS), plus end-to-end checks of ingestion and the
#                publish -> re-queue bridge on the real database (R37).
# How to run: make test-db (throwaway database only, never Supabase; see
#             docs/runbooks/local-setup.md). Skipped otherwise.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Knowledge/unanswered isolation and real-database flows."""

# From dataclasses — replace = copy with some fields changed.
from dataclasses import replace

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# pytest — the test framework.
import pytest

# From sqlalchemy — text = a raw SQL snippet.
from sqlalchemy import text

# From sqlalchemy.exc — DBAPIError = an error raised by the database (here: RLS refusing).
from sqlalchemy.exc import DBAPIError

# From sqlalchemy.ext.asyncio — AsyncEngine; AsyncSession; async_sessionmaker.
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# From tests.contracts.test_knowledge_repository_contract — vec = repeatable 1,536-number vector.
from tests.contracts.test_knowledge_repository_contract import vec

# From tests.db_fixtures — requires_db = skip unless a real Postgres is configured.
from tests.db_fixtures import requires_db

# From tests.fakes.builders — make_config = a valid BotConfig.
from tests.fakes.builders import make_config

# From tests.fakes.knowledge — FakeCrawler; FakeParser (fixed pages).
from tests.fakes.knowledge import FakeCrawler, FakeParser

# From tests.fakes.providers — FakeEmbedder; InMemoryObjectStore.
from tests.fakes.providers import FakeEmbedder, InMemoryObjectStore

# From saathi.bootstrap.knowledge_bridge — the cross-module bridges under test.
from saathi.bootstrap.knowledge_bridge import (
    PublishedChunkingPolicySource,
    RequeueSourcesOnChunkingChange,
    TenancyBotDirectory,
    build_ingestion_service,
)

# From saathi.modules.conversation.adapters.unanswered_repository — SqlAlchemyUnansweredLog.
from saathi.modules.conversation.adapters.unanswered_repository import SqlAlchemyUnansweredLog

# From saathi.modules.conversation.ports.unanswered — UnansweredQuestion; UnansweredReason.
from saathi.modules.conversation.ports.unanswered import UnansweredQuestion, UnansweredReason

# From saathi.modules.knowledge.adapters.chunk_repository — SqlAlchemyChunkRepository.
from saathi.modules.knowledge.adapters.chunk_repository import SqlAlchemyChunkRepository

# From saathi.modules.knowledge.adapters.faq_repository — SqlAlchemyFaqRepository.
from saathi.modules.knowledge.adapters.faq_repository import SqlAlchemyFaqRepository

# From saathi.modules.knowledge.adapters.source_repository — SqlAlchemySourceRepository.
from saathi.modules.knowledge.adapters.source_repository import SqlAlchemySourceRepository

# From saathi.modules.knowledge.application.ingestion — IngestOutcome.
from saathi.modules.knowledge.application.ingestion import IngestOutcome

# From saathi.modules.knowledge.domain.chunking — Chunk; ChunkingPolicy.
from saathi.modules.knowledge.domain.chunking import Chunk, ChunkingPolicy

# From saathi.modules.knowledge.domain.entities — Source; SourceStatus.
from saathi.modules.knowledge.domain.entities import Source, SourceStatus

# From saathi.modules.knowledge.domain.faq — Faq.
from saathi.modules.knowledge.domain.faq import Faq

# From saathi.modules.tenancy.domain.bot_config — RetrievalSettings.
from saathi.modules.tenancy.domain.bot_config import RetrievalSettings

# From saathi.platform.db.after_commit — AfterCommit = work run after COMMIT.
from saathi.platform.db.after_commit import AfterCommit

# From saathi.platform.db.tenant_context — tenant_session = a session locked to one tenant (RLS).
from saathi.platform.db.tenant_context import tenant_session

# Every test here needs real Postgres.
pytestmark = [pytest.mark.integration, requires_db]

# Two tenants...
TENANT_A, TENANT_B = uuid4(), uuid4()
# ...with one bot each.
BOT_A, BOT_B = uuid4(), uuid4()


# A stand-in ARQ pool that records the jobs it was given.
class RecordingPool:
    """Records enqueue_job calls instead of talking to Redis."""

    # Start with no jobs.
    def __init__(self) -> None:
        # The positional arguments of each job.
        self.jobs: list[tuple[Any, ...]] = []

    # Same signature as ArqRedis.enqueue_job.
    async def enqueue_job(self, *args: Any, **kwargs: Any) -> None:
        # Record it.
        self.jobs.append(args)


# Two tenants, one bot each (inserted as the owner, like an operator would).
@pytest.fixture
async def seeded(owner_engine: AsyncEngine) -> None:
    """Two tenants, one bot each."""
    # One owner transaction (the owner bypasses RLS: used only to seed).
    async with owner_engine.begin() as conn:
        # For each tenant and its bot...
        for tenant, bot in ((TENANT_A, BOT_A), (TENANT_B, BOT_B)):
            # ...the tenant row...
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:t, :n)"),
                {"t": tenant, "n": str(tenant)},
            )
            # ...and the bot row.
            await conn.execute(
                text(
                    "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                    "VALUES (:b, :t, 'Mitra', ARRAY['en'], :k)"
                ),
                {"b": bot, "t": tenant, "k": f"pk_{uuid4().hex}"},
            )


# Tenant B stores a source, a chunk and an FAQ through RLS; returns the source.
async def _seed_b_knowledge(app_sessionmaker: async_sessionmaker[AsyncSession]) -> Source:
    # Tenant B's source.
    source = Source(
        id=uuid4(), tenant_id=TENANT_B, bot_id=BOT_B, kind="file", uri="t/b/f.txt", title="b.txt"
    )
    # A transaction locked to tenant B.
    async with tenant_session(app_sessionmaker, TENANT_B) as s:
        # Save the source.
        await SqlAlchemySourceRepository(s).add(source)
        # One 'secret' chunk.
        await SqlAlchemyChunkRepository(s).replace_for_source(
            source, [Chunk(index=0, text="secret price 999")], [vec("secret price 999")]
        )
        # One 'secret' FAQ.
        await SqlAlchemyFaqRepository(s).add(
            Faq(id=uuid4(), tenant_id=TENANT_B, bot_id=BOT_B, question="secret?", answer="999"),
            vec("secret?"),
        )
    # The source.
    return source


# 🔒 Tenant A finds nothing of tenant B's, even when asking for B's ids directly.
async def test_tenant_a_cannot_find_tenant_b_knowledge_even_by_asking_for_b(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # B's data.
    source = await _seed_b_knowledge(app_sessionmaker)
    # A transaction locked to tenant A.
    async with tenant_session(app_sessionmaker, TENANT_A) as s:
        # The repositories on A's session.
        chunks, faqs, sources = (
            SqlAlchemyChunkRepository(s),
            SqlAlchemyFaqRepository(s),
            SqlAlchemySourceRepository(s),
        )
        # Vector search with B's ids: RLS returns nothing.
        assert await chunks.vector_search(TENANT_B, BOT_B, vec("secret price 999"), 10) == []
        # Keyword search with B's ids: nothing.
        assert await chunks.keyword_search(TENANT_B, BOT_B, "secret price", 10) == []
        # FAQ match with B's ids: nothing.
        assert await faqs.best_match(TENANT_B, BOT_B, vec("secret?")) is None
        # B's source by id: nothing.
        assert await sources.get(TENANT_B, source.id) is None
        # B's bot doesn't 'exist' for A...
        assert await TenancyBotDirectory(s).exists(TENANT_B, BOT_B) is False
        # ...while A's own bot does.
        assert await TenancyBotDirectory(s).exists(TENANT_A, BOT_A) is True


# 🔒 With no tenant set, the app role sees no knowledge rows at all (fail closed).
async def test_no_tenant_context_sees_no_knowledge(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # B's data exists.
    await _seed_b_knowledge(app_sessionmaker)
    # A plain session: no tenant bound.
    async with app_sessionmaker() as s:
        # Every Phase 2 table...
        for table in ("sources", "chunks", "faqs", "unanswered_questions"):
            # ...counts zero rows.
            assert (await s.execute(text(f"SELECT count(*) FROM {table}"))).scalar() == 0, table  # noqa: S608 - fixed table names


# 🔒 Tenant A can't write an unanswered row that belongs to tenant B.
async def test_tenant_a_cannot_write_unanswered_rows_for_tenant_b(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # A record claiming to be tenant B's.
    item = UnansweredQuestion(TENANT_B, BOT_B, "q", "en", UnansweredReason.NO_RESULTS, None, None)
    # RLS refuses it...
    with pytest.raises(DBAPIError, match="row-level security"):
        # ...inside tenant A's transaction.
        async with tenant_session(app_sessionmaker, TENANT_A) as s:
            # Try to store it.
            await SqlAlchemyUnansweredLog(s).record(item)
    # Tenant B itself can store it.
    async with tenant_session(app_sessionmaker, TENANT_B) as s:
        # Store it.
        await SqlAlchemyUnansweredLog(s).record(item)
        # It is there, with its reason.
        assert (
            await s.execute(text("SELECT reason FROM unanswered_questions"))
        ).scalar() == "no_results"


# Full ingestion on the real database; a second run of the same file creates zero chunks.
async def test_ingestion_end_to_end_on_postgres_is_idempotent(
    seeded: None, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # File storage.
    store = InMemoryObjectStore()
    # Tenant A's storage key.
    key = f"t/{TENANT_A}/bots/{BOT_A}/files/fees.txt"
    # The stored bytes.
    await store.put(key, b"bytes", "text/plain")
    # A queued source for them.
    source = Source(
        id=uuid4(), tenant_id=TENANT_A, bot_id=BOT_A, kind="file", uri=key, title="fees.txt"
    )
    # Saved through RLS.
    async with tenant_session(app_sessionmaker, TENANT_A) as s:
        # Save it.
        await SqlAlchemySourceRepository(s).add(source)
    # The real ingestion wiring (SQL unit of work, published-config policy reader).
    service = build_ingestion_service(
        sessionmaker=app_sessionmaker,
        store=store,
        parsers={
            ".txt": FakeParser(["# Fees\n\nGST filing costs 500 rupees.\n\nOffice opens at 10."])
        },
        crawler=FakeCrawler(),
        embedder=FakeEmbedder(dimensions=1536),
        pool=RecordingPool(),
    )
    # First run: done.
    assert await service.ingest(TENANT_A, source.id) is IngestOutcome.DONE
    # Look at the result as tenant A.
    async with tenant_session(app_sessionmaker, TENANT_A) as s:
        # The bot's source list.
        listing = (await SqlAlchemySourceRepository(s).list_for_bot(TENANT_A, BOT_A, 5))[0]
        # The chunk row ids now.
        ids_before = set((await s.execute(text("SELECT id FROM chunks"))).scalars())
        # Real full-text search finds the GST chunk.
        hits = await SqlAlchemyChunkRepository(s).keyword_search(TENANT_A, BOT_A, "GST fee", 5)
        # Put the source back in the queue (like Re-sync).
        source_row = await SqlAlchemySourceRepository(s).get_for_update(TENANT_A, source.id)
        # It exists.
        assert source_row is not None
        # ready -> queued.
        source_row.requeue()
        # Save.
        await SqlAlchemySourceRepository(s).save(source_row)
    # Ready, with chunks and a sync time.
    assert (
        listing.source.status is SourceStatus.READY
        and listing.chunk_count >= 1
        and listing.synced_at
    )
    # The hit cites the file name.
    assert hits and hits[0].source_title == "fees.txt"
    # Same file again: unchanged...
    assert await service.ingest(TENANT_A, source.id) is IngestOutcome.UNCHANGED
    # ...and exactly the same chunk rows remain (zero new chunks).
    async with tenant_session(app_sessionmaker, TENANT_A) as s:
        # Same ids as before.
        assert set((await s.execute(text("SELECT id FROM chunks"))).scalars()) == ids_before


# The published-policy reader and the publish -> re-queue bridge on the real database.
async def test_published_chunking_policy_and_publish_requeue_bridge(
    seeded: None, owner_engine: AsyncEngine, app_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    # A ready source for bot A.
    source = Source(
        id=uuid4(),
        tenant_id=TENANT_A,
        bot_id=BOT_A,
        kind="file",
        uri="t/a/f.txt",
        status=SourceStatus.READY,
    )
    # Save it as tenant A.
    async with tenant_session(app_sessionmaker, TENANT_A) as s:
        # Save.
        await SqlAlchemySourceRepository(s).add(source)
        # Nothing published yet: the platform defaults.
        assert (
            await PublishedChunkingPolicySource(s).policy_for(TENANT_A, BOT_A) == ChunkingPolicy()
        )
    # Records the jobs the bridge sends.
    pool = RecordingPool()
    # The config that was live before.
    old = make_config()
    # A new config that changes only a threshold.
    unchanged = replace(old, retrieval=RetrievalSettings(confidence_threshold=0.5))
    # A new config that changes the chunk size.
    changed = replace(old, retrieval=RetrievalSettings(chunk_size_tokens=500))
    # Publish the threshold change...
    hooks = AfterCommit()
    # ...inside tenant A's transaction...
    async with tenant_session(app_sessionmaker, TENANT_A) as s:
        # ...the bridge reacts.
        await RequeueSourcesOnChunkingChange(s, hooks, pool).on_published(
            TENANT_A, BOT_A, old, unchanged
        )
    # 'After commit'.
    await hooks.run()
    # Nothing re-queued.
    assert pool.jobs == []
    # Publish the chunk-size change...
    hooks = AfterCommit()
    # ...inside tenant A's transaction...
    async with tenant_session(app_sessionmaker, TENANT_A) as s:
        # ...the bridge reacts...
        await RequeueSourcesOnChunkingChange(s, hooks, pool).on_published(
            TENANT_A, BOT_A, old, changed
        )
        # ...but sends nothing before the commit.
        assert pool.jobs == []
    # 'After commit'.
    await hooks.run()
    # Now the job for the ready source was sent.
    assert pool.jobs == [("ingest_source", str(TENANT_A), str(source.id))]
    # And the source is back in the queue.
    async with tenant_session(app_sessionmaker, TENANT_A) as s:
        # Load it.
        got = await SqlAlchemySourceRepository(s).get(TENANT_A, source.id)
        # Queued.
        assert got is not None and got.status is SourceStatus.QUEUED

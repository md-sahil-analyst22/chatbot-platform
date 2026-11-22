# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The knowledge use cases behind the endpoints: SourceService (upload, crawl,
#                resync, delete), BotResyncService (re-queue after a chunking change),
#                FaqService, and the lookup (FAQ override, RRF hybrid search, rerank, degraded
#                mode).
# 🔒 Covers roles (403), other tenant / other bot (404) and the tenant always coming from the
#    principal (R8).
# How to run: cd backend && uv run pytest tests/unit/test_knowledge_services.py (no database).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SourceService, BotResyncService, FaqService, KnowledgeSearchService."""

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.knowledge — in-memory stand-ins for the Phase 2 ports.
from tests.fakes.knowledge import (
    FakeBotDirectory,
    InMemoryChunkRepository,
    InMemoryFaqRepository,
    InMemorySourceRepository,
    RecordingPostCommit,
    RecordingQueue,
)

# From tests.fakes.providers — vendor fakes: FakeEmbedder; FakeReranker (word overlap);
#   InMemoryObjectStore (files in a dict).
from tests.fakes.providers import FakeEmbedder, FakeReranker, InMemoryObjectStore

# From saathi.modules.knowledge.application.faq_service — FAQ use cases: FaqService.
from saathi.modules.knowledge.application.faq_service import FaqService

# From saathi.modules.knowledge.application.retrieval — the lookup: KnowledgeSearchService;
#   SearchSettings = its knobs; reciprocal_rank_fusion = merge two ranked lists.
from saathi.modules.knowledge.application.retrieval import (
    KnowledgeSearchService,
    SearchSettings,
    reciprocal_rank_fusion,
)

# From saathi.modules.knowledge.application.source_service — source use cases:
#   BotResyncService = re-queue a bot's sources; SourceService; document_key = storage key.
from saathi.modules.knowledge.application.source_service import (
    BotResyncService,
    SourceService,
    document_key,
)

# From saathi.modules.knowledge.domain.chunking — Chunk = one passage.
from saathi.modules.knowledge.domain.chunking import Chunk

# From saathi.modules.knowledge.domain.crawl — CrawlOptions = one crawl's settings.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.domain.entities — Source; SourceStatus.
from saathi.modules.knowledge.domain.entities import Source, SourceStatus

# From saathi.modules.knowledge.domain.faq — Faq = one question + exact answer.
from saathi.modules.knowledge.domain.faq import Faq

# From saathi.modules.knowledge.ports.repositories — ChunkHit = one search hit.
from saathi.modules.knowledge.ports.repositories import ChunkHit

# From saathi.platform.errors — our error types: AuthorizationError = 403; ConflictError = 409;
#   NotFoundError = 404; ProviderError = a vendor failed; ValidationError = 422.
from saathi.platform.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ProviderError,
    ValidationError,
)

# From saathi.platform.security.auth — who is calling: Principal; Role.
from saathi.platform.security.auth import Principal, Role

# Two tenants and two bots of the first tenant.
TENANT, BOT, OTHER_TENANT, OTHER_BOT = uuid4(), uuid4(), uuid4(), uuid4()
# An admin of the first tenant.
ADMIN = Principal(user_id="u1", tenant_id=TENANT, role=Role.ADMIN)
# A viewer of the first tenant.
VIEWER = Principal(user_id="u2", tenant_id=TENANT, role=Role.VIEWER)


# SourceService wired to fakes.
class Sources:
    """Everything a source test may look at."""

    # Build it.
    def __init__(self) -> None:
        # Source storage.
        self.repo = InMemorySourceRepository()
        # File storage.
        self.store = InMemoryObjectStore()
        # Records queued jobs.
        self.queue = RecordingQueue()
        # Collects post-commit work (run it to 'commit').
        self.post_commit = RecordingPostCommit()
        # The real service; the tenant has BOT and OTHER_BOT; another tenant has a bot too.
        self.service = SourceService(
            sources=self.repo,
            bots=FakeBotDirectory({(TENANT, BOT), (TENANT, OTHER_BOT), (OTHER_TENANT, uuid4())}),
            store=self.store,
            queue=self.queue,
            post_commit=self.post_commit,
        )


# Upload: bytes stored under a tenant-prefixed key, job queued.
async def test_upload_stores_bytes_under_a_tenant_prefixed_key_and_queues_a_job() -> None:
    # Service on fakes.
    s = Sources()
    # Upload a text file with a space in its name.
    source = await s.service.upload(ADMIN, BOT, "Fee List.txt", b"GST 500")
    # Tenant from the principal; the key uses the cleaned name (R8, storage rule).
    assert source.tenant_id == TENANT and source.uri == document_key(TENANT, BOT, "Fee_List.txt")
    # The key starts with the tenant; the title keeps the original name.
    assert source.uri.startswith(f"t/{TENANT}/") and source.title == "Fee List.txt"
    # The bytes are stored.
    assert await s.store.get(source.uri) == b"GST 500"
    # One job was queued for it.
    assert s.queue.jobs == [(TENANT, source.id)]


# Uploading the same name again replaces that source (no second row).
async def test_reupload_with_the_same_name_replaces_the_source() -> None:
    # Service on fakes.
    s = Sources()
    # First upload.
    first = await s.service.upload(ADMIN, BOT, "fees.txt", b"v1")
    # Load it...
    stored = await s.repo.get(TENANT, first.id)
    # ...(it exists)...
    assert stored is not None
    # ...pretend the worker processed it...
    stored.start_processing()
    # ...successfully...
    stored.mark_ready("h")
    # ...and save.
    await s.repo.save(stored)
    # Upload the same name again with new bytes.
    second = await s.service.upload(ADMIN, BOT, "fees.txt", b"v2")
    # Same source, back in the queue.
    assert second.id == first.id and second.status is SourceStatus.QUEUED
    # New bytes stored; still only one row.
    assert await s.store.get(first.uri) == b"v2" and len(s.repo.rows) == 1


# A file being processed can't be swapped under the worker.
async def test_reupload_while_processing_is_409() -> None:
    # Service on fakes.
    s = Sources()
    # First upload.
    first = await s.service.upload(ADMIN, BOT, "fees.txt", b"v1")
    # Load it...
    stored = await s.repo.get(TENANT, first.id)
    # ...(it exists)...
    assert stored is not None
    # ...the worker is processing it...
    stored.start_processing()
    # ...saved.
    await s.repo.save(stored)
    # A second upload now is a conflict...
    with pytest.raises(ConflictError):
        # ...409.
        await s.service.upload(ADMIN, BOT, "fees.txt", b"v2")


# Roles, bot ownership and file checks are enforced before anything is stored.
async def test_upload_permissions_and_validation() -> None:
    # Service on fakes.
    s = Sources()
    # Viewers can't upload...
    with pytest.raises(AuthorizationError):
        # ...403.
        await s.service.upload(VIEWER, BOT, "a.txt", b"x")
    # An unknown (or another tenant's) bot...
    with pytest.raises(NotFoundError):
        # ...404.
        await s.service.upload(ADMIN, uuid4(), "a.txt", b"x")
    # An unsupported file...
    with pytest.raises(ValidationError):
        # ...422.
        await s.service.upload(ADMIN, BOT, "a.exe", b"MZ\x00")
    # Nothing was stored and nothing was queued.
    assert s.store._objects == {} and s.queue.jobs == []


# Adding a website queues a job; adding it twice is refused.
async def test_add_website_and_duplicate_is_409() -> None:
    # Service on fakes.
    s = Sources()
    # Add a website.
    src = await s.service.add_website(ADMIN, BOT, CrawlOptions("https://shop.example/"))
    # A website source with its settings, and a queued job.
    assert src.kind == "url" and src.crawl is not None and s.queue.jobs == [(TENANT, src.id)]
    # The same site again...
    with pytest.raises(ConflictError):
        # ...409 (use re-sync instead).
        await s.service.add_website(ADMIN, BOT, CrawlOptions("https://shop.example/"))


# 🔒 A source is invisible through another bot's path or another tenant's login.
async def test_items_of_another_bot_or_tenant_are_404() -> None:
    # Service on fakes.
    s = Sources()
    # A source of BOT.
    src = await s.service.upload(ADMIN, BOT, "a.txt", b"x")
    # Same tenant, wrong bot in the path...
    with pytest.raises(NotFoundError):
        # ...404.
        await s.service.get_source(ADMIN, OTHER_BOT, src.id)
    # An owner of another tenant.
    other = Principal(user_id="x", tenant_id=OTHER_TENANT, role=Role.OWNER)
    # Can't read it...
    with pytest.raises(NotFoundError):
        # ...404.
        await s.service.get_source(other, BOT, src.id)
    # ...and can't delete it.
    with pytest.raises(NotFoundError):
        # ...404.
        await s.service.delete(other, BOT, src.id)


# Re-sync: re-sends a queued job, refuses while processing, admins only.
async def test_resync_rules() -> None:
    # Service on fakes.
    s = Sources()
    # A queued source (its job was sent once).
    src = await s.service.upload(ADMIN, BOT, "a.txt", b"x")
    # Re-sync while still queued (e.g. the job was lost)...
    await s.service.resync(ADMIN, BOT, src.id)
    # ...sends the job again.
    assert s.queue.jobs == [(TENANT, src.id), (TENANT, src.id)]
    # Load it...
    stored = await s.repo.get(TENANT, src.id)
    # ...(it exists)...
    assert stored is not None
    # ...now it is processing...
    stored.start_processing()
    # ...saved.
    await s.repo.save(stored)
    # Re-sync now...
    with pytest.raises(ConflictError):
        # ...409.
        await s.service.resync(ADMIN, BOT, src.id)
    # A viewer...
    with pytest.raises(AuthorizationError):
        # ...can't re-sync (403).
        await s.service.resync(VIEWER, BOT, src.id)


# The stored file is deleted only after the database delete commits.
async def test_delete_removes_the_stored_file_only_after_commit() -> None:
    # Service on fakes.
    s = Sources()
    # A source with a stored file.
    src = await s.service.upload(ADMIN, BOT, "a.txt", b"x")
    # Delete it.
    await s.service.delete(ADMIN, BOT, src.id)
    # The row is gone, but the file is still there until commit...
    assert src.id not in s.repo.rows and src.uri in s.store._objects
    # ...'commit'...
    await s.post_commit.run()
    # ...and now the file is gone too.
    assert src.uri not in s.store._objects


# Listing works for the caller's bot and 404s for an unknown bot.
async def test_list_requires_the_callers_bot() -> None:
    # Service on fakes.
    s = Sources()
    # One source.
    await s.service.upload(ADMIN, BOT, "a.txt", b"x")
    # A viewer sees it.
    assert len(await s.service.list_sources(VIEWER, BOT)) == 1
    # An unknown bot...
    with pytest.raises(NotFoundError):
        # ...404 (not an empty list).
        await s.service.list_sources(VIEWER, uuid4())


# After a chunk-settings change only finished sources are queued again.
async def test_bot_resync_requeues_only_finished_sources() -> None:
    # Source storage and a job recorder.
    repo, queue = InMemorySourceRepository(), RecordingQueue()
    # One source in each status.
    states = [SourceStatus.READY, SourceStatus.FAILED, SourceStatus.QUEUED, SourceStatus.PROCESSING]
    # Their ids, in the same order.
    ids = []
    # Create them...
    for i, status in enumerate(states):
        # ...one source per status...
        src = Source(
            id=uuid4(), tenant_id=TENANT, bot_id=BOT, kind="file", uri=f"t/{i}", status=status
        )
        # ...saved...
        await repo.add(src)
        # ...and remembered.
        ids.append(src.id)
    # A ready source of ANOTHER bot (must never be touched).
    await repo.add(
        Source(
            id=uuid4(),
            tenant_id=TENANT,
            bot_id=OTHER_BOT,
            kind="file",
            uri="t/o",
            status=SourceStatus.READY,
        )
    )
    # Re-queue the bot.
    count = await BotResyncService(sources=repo, queue=queue).requeue_bot(TENANT, BOT)
    # Only the ready and failed ones were queued.
    assert count == 2 and {sid for _, sid in queue.jobs} == {ids[0], ids[1]}
    # The processing one is left alone (it re-queues itself when it finishes).
    assert repo.rows[ids[3]].status is SourceStatus.PROCESSING


# FaqService wired to fakes.
class Faqs:
    """Everything an FAQ test may look at."""

    # Build it.
    def __init__(self) -> None:
        # FAQ storage.
        self.repo = InMemoryFaqRepository()
        # The embedder (records the last task).
        self.embedder = FakeEmbedder()
        # The real service; only BOT exists.
        self.service = FaqService(
            faqs=self.repo, bots=FakeBotDirectory({(TENANT, BOT)}), embedder=self.embedder
        )


# A new FAQ's question is embedded as a 'query'.
async def test_faq_create_embeds_the_question_as_a_query() -> None:
    # Service on fakes.
    f = Faqs()
    # Create an FAQ.
    faq = await f.service.create(ADMIN, BOT, "Office hours?", "10 to 7")
    # Tenant from the principal; embedded as a question.
    assert faq.tenant_id == TENANT and f.embedder.last_task == "query"
    # A vector was stored with it.
    assert f.repo.rows[faq.id][1] is not None


# The question is re-embedded only when it changes.
async def test_faq_update_reembeds_only_when_the_question_changes() -> None:
    # Service on fakes.
    f = Faqs()
    # Create an FAQ.
    faq = await f.service.create(ADMIN, BOT, "Office hours?", "10 to 7")
    # Its vector now.
    vector_before = f.repo.rows[faq.id][1]
    # Change only the answer and switch it off.
    await f.service.update(ADMIN, BOT, faq.id, answer="9 to 6", is_active=False)
    # Same vector; switched off.
    assert f.repo.rows[faq.id][1] == vector_before and f.repo.rows[faq.id][0].is_active is False
    # Change the question.
    await f.service.update(ADMIN, BOT, faq.id, question="When do you open?")
    # A new vector.
    assert f.repo.rows[faq.id][1] != vector_before


# 🔒 FAQ roles and isolation.
async def test_faq_permissions_and_isolation() -> None:
    # Service on fakes.
    f = Faqs()
    # A viewer...
    with pytest.raises(AuthorizationError):
        # ...can't create (403).
        await f.service.create(VIEWER, BOT, "q", "a")
    # An unknown bot...
    with pytest.raises(NotFoundError):
        # ...404.
        await f.service.create(ADMIN, uuid4(), "q", "a")
    # An FAQ of BOT.
    faq = await f.service.create(ADMIN, BOT, "q", "a")
    # Through another bot's path...
    with pytest.raises(NotFoundError):
        # ...404.
        await f.service.delete(ADMIN, OTHER_BOT, faq.id)
    # Another tenant's owner...
    other = Principal(user_id="x", tenant_id=OTHER_TENANT, role=Role.OWNER)
    # ...can't change it.
    with pytest.raises(NotFoundError):
        # ...404.
        await f.service.update(other, BOT, faq.id, answer="hacked")


# A search hit named after its text.
def _hit(name: str) -> ChunkHit:
    # Minimal hit with a random id.
    return ChunkHit(
        chunk_id=uuid4(),
        source_id=uuid4(),
        source_title=name,
        text=name,
        section="",
        page=None,
        url=None,
        score=0.0,
    )


# RRF: a chunk found by both searches beats chunks found by one.
def test_rrf_rewards_chunks_found_by_both_searches() -> None:
    # Three hits.
    a, b, c = _hit("a"), _hit("b"), _hit("c")
    # 'a' is first in one list and second in the other.
    fused = reciprocal_rank_fusion([[a, b], [c, a]])
    # 'a' wins.
    assert fused[0].hit is a
    # Its score is 1/(60+1) + 1/(60+2).
    assert fused[0].score == pytest.approx(1 / 61 + 1 / 62)
    # Every hit appears once.
    assert {p.hit.text for p in fused} == {"a", "b", "c"}


# KnowledgeSearchService wired to fakes.
class Search:
    """One source of three chunks; FAQs added by tests."""

    # Build it (the reranker can be made to fail).
    def __init__(self, reranker_mode: str = "ok") -> None:
        # Chunk storage.
        self.chunks = InMemoryChunkRepository()
        # FAQ storage.
        self.faqs = InMemoryFaqRepository()
        # Embedder.
        self.embedder = FakeEmbedder()
        # The real lookup.
        self.service = KnowledgeSearchService(
            chunks=self.chunks,
            faqs=self.faqs,
            embedder=self.embedder,
            reranker=FakeReranker(reranker_mode),  # type: ignore[arg-type]  # test modes
        )

    # Store three chunks for BOT.
    async def seed(self) -> None:
        # Their source.
        source = Source(
            id=uuid4(), tenant_id=TENANT, bot_id=BOT, kind="file", uri="t/a", title="fees.pdf"
        )
        # Their texts.
        texts = [
            "gst filing fee is 500 rupees",
            "office hours are 10 to 7",
            "we are closed on sunday",
        ]
        # Their vectors.
        vectors = await self.embedder.embed(texts, task="document")
        # Store them.
        await self.chunks.replace_for_source(
            source, [Chunk(index=i, text=t) for i, t in enumerate(texts)], vectors
        )


# ⭐ A matching FAQ wins and the chunks aren't used.
async def test_faq_wins_above_threshold_without_searching_chunks() -> None:
    # Lookup on fakes...
    s = Search()
    # ...with chunks.
    await s.seed()
    # An FAQ whose question is exactly the asked question (similarity 1.0).
    faq = Faq(id=uuid4(), tenant_id=TENANT, bot_id=BOT, question="gst fee?", answer="₹500 exactly")
    # Store it with its vector.
    await s.faqs.add(faq, (await s.embedder.embed(["gst fee?"], task="query"))[0])
    # Ask that question.
    result = await s.service.lookup(TENANT, BOT, "gst fee?", SearchSettings(faq_threshold=0.9))
    # The FAQ answer, and no passages.
    assert (
        result.faq is not None and result.faq.faq.answer == "₹500 exactly" and result.passages == []
    )


# 🔍 Hybrid search + rerank: best passage first, confidence = its score.
async def test_hybrid_search_reranks_and_reports_confidence() -> None:
    # Lookup on fakes...
    s = Search()
    # ...with chunks.
    await s.seed()
    # Ask, keeping the top 2.
    result = await s.service.lookup(TENANT, BOT, "gst filing fee", SearchSettings(rerank_top_n=2))
    # Reranked, no FAQ, two passages.
    assert result.reranked and result.faq is None and len(result.passages) == 2
    # The GST passage is first.
    assert result.passages[0].hit.text.startswith("gst filing fee")
    # Confidence is the best reranker score.
    assert result.confidence == result.passages[0].score


# Reranker down: results are kept but flagged, with no confidence.
async def test_reranker_down_degrades_and_is_flagged() -> None:
    # A failing reranker...
    s = Search(reranker_mode="error")
    # ...with chunks.
    await s.seed()
    # Ask.
    result = await s.service.lookup(TENANT, BOT, "gst filing fee", SearchSettings(rerank_top_n=2))
    # Not reranked, no confidence (the guardrail will say "not sure"), still two passages.
    assert result.reranked is False and result.confidence is None and len(result.passages) == 2


# 🔒 Another tenant finds nothing; an empty question searches nothing.
async def test_other_tenant_finds_nothing_and_empty_question_short_circuits() -> None:
    # Lookup on fakes...
    s = Search()
    # ...with chunks for TENANT.
    await s.seed()
    # Asking as another tenant.
    result = await s.service.lookup(OTHER_TENANT, BOT, "gst filing fee", SearchSettings())
    # Nothing.
    assert result.passages == [] and result.faq is None
    # Only spaces: nothing.
    assert (await s.service.lookup(TENANT, BOT, "   ", SearchSettings())).passages == []


# Embedder down: search is impossible, so a provider error is raised.
async def test_embedder_down_raises_provider_error() -> None:
    # Lookup on fakes...
    s = Search()
    # ...rebuilt with a failing embedder.
    s.service = KnowledgeSearchService(
        chunks=s.chunks, faqs=s.faqs, embedder=FakeEmbedder("error"), reranker=FakeReranker()
    )
    # A provider error...
    with pytest.raises(ProviderError):
        # ...from the lookup.
        await s.service.lookup(TENANT, BOT, "gst", SearchSettings())


# Search knobs are bounded.
def test_search_settings_bounds() -> None:
    # Each of these is out of range...
    for kwargs in (
        {"vector_top_k": 0},
        {"keyword_top_k": 51},
        {"rerank_top_n": 11},
        {"faq_threshold": 2.0},
    ):
        # ...and refused.
        with pytest.raises(ValidationError):
            # Build it.
            SearchSettings(**kwargs)  # type: ignore[arg-type]  # deliberately wrong values

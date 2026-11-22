# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The 'bridges' between modules for Phase 2. Modules never import each other (R4); each
#       one declares what it needs as a port, and this file (part of the composition root) plugs
#       in an implementation backed by the other module:
#   knowledge needs   BotDirectory          <- backed by tenancy's bot repository
#   knowledge needs   ChunkingPolicySource  <- backed by tenancy's published bot config
#   tenancy needs     ConfigPublishedHook   <- backed by knowledge (re-queue sources when the
#                                              chunk size/overlap changed)
#   conversation needs KnowledgeRetriever   <- backed by knowledge's search service
# Every bridge works on the SAME database session as its caller, so it shares the caller's
#   tenant-bound transaction (RLS) and commits or rolls back with it.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Cross-module adapters for Phase 2 (composition root only)."""

# From typing — type-hint helpers: Any = any type (ARQ pool).
from typing import Any

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From sqlalchemy.ext.asyncio — async database sessions: AsyncSession = one session;
#   async_sessionmaker = makes sessions.
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# From saathi.modules.conversation.adapters.unanswered_repository — SQL unanswered log.
from saathi.modules.conversation.adapters.unanswered_repository import SqlAlchemyUnansweredLog

# From saathi.modules.conversation.application.answer_service — the answer use case.
from saathi.modules.conversation.application.answer_service import AnswerService

# From saathi.modules.conversation.application.llm_resolver — per-bot model client: LlmResolver.
from saathi.modules.conversation.application.llm_resolver import LlmResolver

# From saathi.modules.conversation.ports.retrieval — conversation's retrieval types.
from saathi.modules.conversation.ports.retrieval import (
    FaqHit,
    Passage,
    Retrieval,
    RetrievalRequest,
)

# From saathi.modules.knowledge.adapters.arq_queue — job queue adapter: ArqIngestQueue.
from saathi.modules.knowledge.adapters.arq_queue import ArqIngestQueue

# From saathi.modules.knowledge.adapters.chunk_repository — SQL chunks.
from saathi.modules.knowledge.adapters.chunk_repository import SqlAlchemyChunkRepository

# From saathi.modules.knowledge.adapters.faq_repository — SQL FAQs.
from saathi.modules.knowledge.adapters.faq_repository import SqlAlchemyFaqRepository

# From saathi.modules.knowledge.adapters.source_repository — SQL sources.
from saathi.modules.knowledge.adapters.source_repository import SqlAlchemySourceRepository

# From saathi.modules.knowledge.adapters.unit_of_work — SQL transactions for the worker.
from saathi.modules.knowledge.adapters.unit_of_work import SqlIngestionUnitOfWork

# From saathi.modules.knowledge.application.ingestion — the ingestion use case.
from saathi.modules.knowledge.application.ingestion import IngestionService

# From saathi.modules.knowledge.application.retrieval — knowledge lookup: KnowledgeSearchService;
#   SearchSettings = its knobs.
from saathi.modules.knowledge.application.retrieval import KnowledgeSearchService, SearchSettings

# From saathi.modules.knowledge.application.source_service — system re-queue: BotResyncService.
from saathi.modules.knowledge.application.source_service import BotResyncService

# From saathi.modules.knowledge.domain.chunking — chunk rules: ChunkingPolicy.
from saathi.modules.knowledge.domain.chunking import ChunkingPolicy

# From saathi.modules.knowledge.ports.providers — knowledge vendor contracts.
from saathi.modules.knowledge.ports.providers import (
    DocumentParser,
    Embedder,
    Reranker,
    WebCrawler,
)

# From saathi.modules.tenancy.adapters.config_repository — SQL config versions.
from saathi.modules.tenancy.adapters.config_repository import SqlAlchemyBotConfigRepository

# From saathi.modules.tenancy.adapters.repository — SQL bots.
from saathi.modules.tenancy.adapters.repository import SqlAlchemyBotRepository

# From saathi.modules.tenancy.domain.bot_config — configuration: BotConfig; RetrievalSettings.
from saathi.modules.tenancy.domain.bot_config import BotConfig, RetrievalSettings

# From saathi.platform.config.model_catalog — models tenants may choose: ModelCatalog.
from saathi.platform.config.model_catalog import ModelCatalog

# From saathi.platform.db.after_commit — after-commit hooks: AfterCommit.
from saathi.platform.db.after_commit import AfterCommit

# From saathi.platform.storage — file storage contract: ObjectStore.
from saathi.platform.storage import ObjectStore


# Convert tenancy's retrieval settings into knowledge's chunking policy.
def chunking_policy_from(settings: RetrievalSettings) -> ChunkingPolicy:
    # Same two numbers; ChunkingPolicy validates them again (same ranges).
    return ChunkingPolicy(
        chunk_size_tokens=settings.chunk_size_tokens,
        overlap_ratio=settings.chunk_overlap_ratio,
    )


# knowledge.BotDirectory, backed by tenancy.
class TenancyBotDirectory:
    """Does the bot exist for this tenant? (RLS + explicit tenant filter.)"""

    # Keep the caller's session.
    def __init__(self, session: AsyncSession) -> None:
        # Tenancy's bot repository on the same session.
        self._bots = SqlAlchemyBotRepository(session)

    # True only for the tenant's own bot.
    async def exists(self, tenant_id: UUID, bot_id: UUID) -> bool:
        # Filtered by tenant (R15).
        return await self._bots.get(tenant_id, bot_id) is not None


# knowledge.ChunkingPolicySource, backed by the bot's published config.
class PublishedChunkingPolicySource:
    """The published version's chunk settings; defaults when nothing is published yet."""

    # Keep the caller's session.
    def __init__(self, session: AsyncSession) -> None:
        # Tenancy's config repository on the same session.
        self._configs = SqlAlchemyBotConfigRepository(session)

    # The bot's chunking policy.
    async def policy_for(self, tenant_id: UUID, bot_id: UUID) -> ChunkingPolicy:
        # The live version, if any.
        live = await self._configs.published(tenant_id, bot_id)
        # Defaults until the first publish (the same defaults a new config gets).
        settings = live.config.retrieval if live is not None else RetrievalSettings()
        # Convert.
        return chunking_policy_from(settings)


# tenancy.ConfigPublishedHook, backed by knowledge.
class RequeueSourcesOnChunkingChange:
    """When a publish changes chunk size/overlap, every source of the bot is processed again."""

    # Keep what the re-queue needs.
    def __init__(self, session: AsyncSession, after_commit: AfterCommit, pool: Any) -> None:
        # Knowledge's re-queue use case on the same session; jobs are sent after commit.
        self._resync = BotResyncService(
            sources=SqlAlchemySourceRepository(session),
            queue=ArqIngestQueue(pool, after_commit),
        )

    # React to a publish.
    async def on_published(
        self, tenant_id: UUID, bot_id: UUID, previous: BotConfig | None, current: BotConfig
    ) -> None:
        # What sources were last chunked with: the previous live settings, or the defaults.
        before = previous.retrieval if previous is not None else RetrievalSettings()
        # Unchanged chunking: nothing to redo.
        if not current.retrieval.chunking_differs(before):
            # Done.
            return
        # Re-queue every finished source of the bot (same transaction; jobs after commit).
        await self._resync.requeue_bot(tenant_id, bot_id)


# conversation.KnowledgeRetriever, backed by knowledge's search service.
class KnowledgeRetrieverAdapter:
    """Calls knowledge's lookup and converts the result to conversation's types."""

    # Keep the search service.
    def __init__(self, search: KnowledgeSearchService) -> None:
        # Knowledge lookup (built on the caller's session).
        self._search = search

    # Look a question up.
    async def retrieve(
        self, tenant_id: UUID, bot_id: UUID, question: str, request: RetrievalRequest
    ) -> Retrieval:
        # Knowledge's own settings type.
        settings = SearchSettings(
            vector_top_k=request.vector_top_k,
            keyword_top_k=request.keyword_top_k,
            rerank_top_n=request.rerank_top_n,
            faq_threshold=request.faq_threshold,
        )
        # Run the lookup.
        result = await self._search.lookup(tenant_id, bot_id, question, settings)
        # Convert the FAQ match.
        faq = (
            FaqHit(
                question=result.faq.faq.question,
                answer=result.faq.faq.answer,
                similarity=result.faq.similarity,
            )
            if result.faq is not None
            else None
        )
        # Convert the passages.
        passages = [
            Passage(
                source_title=p.hit.source_title,
                text=p.hit.text,
                section=p.hit.section,
                page=p.hit.page,
                url=p.hit.url,
                score=p.score,
            )
            for p in result.passages
        ]
        # Conversation's result type.
        return Retrieval(
            faq=faq, passages=passages, confidence=result.confidence, reranked=result.reranked
        )


# ───────────────────────────── Builders (worker, evals) ─────────────────────────────


# The ingestion use case for the worker (one instance per worker process).
def build_ingestion_service(
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    store: ObjectStore,
    parsers: dict[str, DocumentParser],
    crawler: WebCrawler,
    embedder: Embedder,
    pool: Any,
) -> IngestionService:
    """Wires IngestionService with SQL repositories and the published-config policy reader."""
    # Short transactions with knowledge repositories + tenancy-backed chunking settings.
    uow = SqlIngestionUnitOfWork(sessionmaker, PublishedChunkingPolicySource)
    # The use case (the worker has no request transaction: follow-up jobs are sent directly).
    return IngestionService(
        uow=uow,
        store=store,
        parsers=parsers,
        crawler=crawler,
        embedder=embedder,
        queue=ArqIngestQueue(pool),
    )


# The answer use case on one tenant-bound session (evals now; the chat path in Phase 3).
def build_answer_service(
    session: AsyncSession,
    *,
    embedder: Embedder,
    reranker: Reranker,
    llm: LlmResolver,
    catalog: ModelCatalog,
) -> AnswerService:
    """Knowledge search + LLM + unanswered log, all on the caller's session/transaction."""
    # Knowledge lookup on this session.
    search = KnowledgeSearchService(
        chunks=SqlAlchemyChunkRepository(session),
        faqs=SqlAlchemyFaqRepository(session),
        embedder=embedder,
        reranker=reranker,
    )
    # The answer use case.
    return AnswerService(
        retriever=KnowledgeRetrieverAdapter(search),
        llm=llm,
        catalog=catalog,
        unanswered=SqlAlchemyUnansweredLog(session),
    )

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Finds what a bot knows about a customer's question (P2.10 - P2.12).
# Steps:
#   1. Embed the question once.
#   2. ⭐ FAQ first (P2.12): the closest active FAQ question; if it is similar enough
#      (the bot's faq_threshold, high by default), its answer wins and we stop here.
#   3. 🔍 Hybrid search (P2.10): vector top-k ('same meaning') + keyword top-k ('same words'),
#      merged with Reciprocal Rank Fusion (RRF): each list votes 1/(60 + rank) for its chunks,
#      so chunks found by both lists rise to the top. Always filtered by tenant AND bot.
#   4. 🎯 Rerank (P2.11): a multilingual reranker re-reads the candidates against the question
#      and keeps the best top-n; its top score is the 'confidence'.
#   If the reranker is down, we keep the RRF order but mark the result as NOT reranked: the
#   answer step then says "I'm not sure" instead of trusting an unscored guess (fail closed).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Knowledge lookup: FAQ override, hybrid search, rerank (P2.10 - P2.12)."""

# From collections.abc — standard type names for collections: Sequence = read-only list type.
from collections.abc import Sequence

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# structlog — structured logging (JSON log lines).
import structlog

# From saathi.modules.knowledge.ports.providers — vendor contracts: Embedder = text -> vectors;
#   Reranker = best documents first.
from saathi.modules.knowledge.ports.providers import Embedder, Reranker

# From saathi.modules.knowledge.ports.repositories — storage contracts: ChunkHit = one found
#   chunk; ChunkRepository = chunks; FaqMatch = closest FAQ; FaqRepository = FAQs.
from saathi.modules.knowledge.ports.repositories import (
    ChunkHit,
    ChunkRepository,
    FaqMatch,
    FaqRepository,
)

# From saathi.platform.errors — our error types: ProviderError = a vendor failed;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import ProviderError, ValidationError

# The logger for this file.
log = structlog.get_logger()

# RRF's standard damping constant (from the original RRF paper; larger = flatter votes).
RRF_K = 60
# Longest question we search for (longer input is cut, not refused: it's a chat message).
MAX_QUERY_CHARS = 2000


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# The per-bot knobs for one lookup (from the bot's published config).
class SearchSettings:
    # How many chunks the vector search returns.
    vector_top_k: int = 20
    # How many chunks the keyword search returns.
    keyword_top_k: int = 20
    # How many chunks survive reranking.
    rerank_top_n: int = 5
    # Minimum FAQ similarity for the FAQ answer to win (0..1).
    faq_threshold: float = 0.9

    # Runs right after __init__: reject invalid values (R20).
    def __post_init__(self) -> None:
        # Both top-k values within 1..50 (bounded cost).
        if not (1 <= self.vector_top_k <= 50 and 1 <= self.keyword_top_k <= 50):
            # 422.
            raise ValidationError("top-k must be between 1 and 50")
        # Rerank top-n within 1..10 (bounded prompt size).
        if not 1 <= self.rerank_top_n <= 10:
            # 422.
            raise ValidationError("rerank top-n must be between 1 and 10")
        # Threshold within 0..1.
        if not 0.0 <= self.faq_threshold <= 1.0:
            # 422.
            raise ValidationError("faq threshold must be between 0 and 1")


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One passage chosen for the answer.
class Passage:
    # The chunk.
    hit: ChunkHit
    # Its final score (reranker relevance if reranked, otherwise the RRF score).
    score: float


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# Everything a lookup found.
class LookupResult:
    # The winning FAQ (when set, `passages` is empty: the FAQ answer is used as-is).
    faq: FaqMatch | None
    # The best passages, best first.
    passages: list[Passage]
    # The reranker's top score (None when not reranked or nothing found).
    confidence: float | None
    # True only if the reranker scored the passages.
    reranked: bool


# Merge ranked lists with Reciprocal Rank Fusion.
def reciprocal_rank_fusion(lists: Sequence[Sequence[ChunkHit]], k: int = RRF_K) -> list[Passage]:
    """Each list gives a chunk 1/(k + rank) (rank starts at 1). Highest total first."""
    # Total votes per chunk id.
    scores: dict[UUID, float] = {}
    # The chunk object for each id (first seen wins; both lists carry the same text).
    hits: dict[UUID, ChunkHit] = {}
    # Every list...
    for ranked in lists:
        # ...every chunk, with its 1-based rank...
        for rank, hit in enumerate(ranked, start=1):
            # ...adds its vote.
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
            # Remember the chunk.
            hits.setdefault(hit.chunk_id, hit)
    # Best total first; ties keep a stable order by id so results are repeatable.
    order = sorted(scores, key=lambda cid: (-scores[cid], str(cid)))
    # As passages with their fused score.
    return [Passage(hit=hits[cid], score=scores[cid]) for cid in order]


# The lookup use case.
class KnowledgeSearchService:
    # Receive every collaborator through the constructor (R21).
    def __init__(
        self,
        *,
        chunks: ChunkRepository,
        faqs: FaqRepository,
        embedder: Embedder,
        reranker: Reranker,
    ) -> None:
        # Chunk search.
        self._chunks = chunks
        # FAQ match.
        self._faqs = faqs
        # Question embedding.
        self._embedder = embedder
        # Reranking.
        self._reranker = reranker

    # Look up a question for one bot. 🔒 tenant_id comes from the verified caller, never input.
    async def lookup(
        self, tenant_id: UUID, bot_id: UUID, question: str, settings: SearchSettings
    ) -> LookupResult:
        """FAQ override first, then hybrid search + rerank. Provider failures of the embedder
        raise ProviderError (nothing can be found without it); a reranker failure degrades."""
        # Bound the input (it's a chat message, so cut rather than refuse).
        query = question.strip()[:MAX_QUERY_CHARS]
        # Nothing to search for.
        if not query:
            # Empty result.
            return LookupResult(faq=None, passages=[], confidence=None, reranked=False)
        # Step 1: one embedding for both the FAQ match and the vector search.
        vector = (await self._embedder.embed([query], task="query"))[0]
        # Step 2: FAQ first.
        match = await self._faqs.best_match(tenant_id, bot_id, vector)
        # Similar enough: the FAQ wins.
        if match is not None and match.similarity >= settings.faq_threshold:
            # Return just the FAQ (confidence = its similarity).
            return LookupResult(faq=match, passages=[], confidence=match.similarity, reranked=True)
        # Step 3a: 'same meaning' candidates.
        by_vector = await self._chunks.vector_search(
            tenant_id, bot_id, vector, settings.vector_top_k
        )
        # Step 3b: 'same words' candidates.
        by_keyword = await self._chunks.keyword_search(
            tenant_id, bot_id, query, settings.keyword_top_k
        )
        # Step 3c: merge.
        fused = reciprocal_rank_fusion([by_vector, by_keyword])
        # Nothing at all.
        if not fused:
            # Empty result (the guardrail will say "I'm not sure").
            return LookupResult(faq=None, passages=[], confidence=None, reranked=False)
        # Step 4: rerank.
        try:
            # Scores for the best top-n candidates, best first.
            ranked = await self._reranker.rerank(
                query, [p.hit.text for p in fused], settings.rerank_top_n
            )
        # Reranker down: degrade to the RRF order, flagged as not reranked.
        except ProviderError as exc:
            # Log the type only.
            log.warning("retrieval.rerank_unavailable", error_type=type(exc).__name__)
            # Best RRF candidates, no confidence.
            return LookupResult(
                faq=None,
                passages=fused[: settings.rerank_top_n],
                confidence=None,
                reranked=False,
            )
        # Map the reranker's positions back to passages with their relevance score.
        passages = [Passage(hit=fused[r.index].hit, score=r.score) for r in ranked]
        # Confidence = the best relevance score (0 if the reranker returned nothing).
        confidence = passages[0].score if passages else 0.0
        # The final result.
        return LookupResult(faq=None, passages=passages, confidence=confidence, reranked=True)

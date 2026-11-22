# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: What the conversation module needs from 'the bot's knowledge': give me a matching FAQ
#       or the best passages for this question, with a confidence score.
# Why its own types: conversation may not import the knowledge module (R4). bootstrap/ plugs in
#   an adapter that calls knowledge and converts its results into these small types.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Knowledge-retrieval port for the conversation module (R4: the asking module declares it)."""

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# The per-bot search knobs (from the bot's published config).
class RetrievalRequest:
    # 'Same meaning' search size.
    vector_top_k: int = 20
    # 'Same words' search size.
    keyword_top_k: int = 20
    # Passages kept after reranking.
    rerank_top_n: int = 5
    # FAQ answer wins at or above this similarity.
    faq_threshold: float = 0.9


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One passage the answer may use.
class Passage:
    # Display title of its source (file name or page title).
    source_title: str
    # The text.
    text: str
    # Heading path ('' if none).
    section: str
    # Page number (None for web/plain text).
    page: int | None
    # Web page address (website sources only).
    url: str | None
    # Relevance score (reranker), higher = better.
    score: float


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# A matching FAQ.
class FaqHit:
    # The FAQ question.
    question: str
    # The exact answer to give.
    answer: str
    # How similar the customer's question is (0..1).
    similarity: float


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# What retrieval found.
class Retrieval:
    # The winning FAQ (when set, passages is empty).
    faq: FaqHit | None
    # Best passages, best first.
    passages: list[Passage]
    # Reranker's top score (None when not reranked or nothing found).
    confidence: float | None
    # True only if a reranker scored the passages (False = degraded, don't trust).
    reranked: bool


# Contract: look a question up in one bot's knowledge.
class KnowledgeRetriever(Protocol):
    # 🔒 tenant_id must come from the verified caller. Raises ProviderError when search itself
    #   is impossible (e.g. the embedding provider is down).
    async def retrieve(
        self, tenant_id: UUID, bot_id: UUID, question: str, request: RetrievalRequest
    ) -> Retrieval: ...

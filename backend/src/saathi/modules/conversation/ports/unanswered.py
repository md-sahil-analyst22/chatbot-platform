# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contract for recording questions the bot could not answer (P2.14). Bot Studio's
#       'Unanswered questions' screen (Phase 5) shows them so the business can fill the gaps.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Unanswered-question log port."""

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID


# Why the bot said "I'm not sure".
class UnansweredReason(StrEnum):
    # Nothing in the knowledge base matched.
    NO_RESULTS = "no_results"
    # Something matched, but the reranker's score was below the bot's threshold.
    LOW_CONFIDENCE = "low_confidence"
    # The model said the context doesn't support an answer (or cited nothing valid).
    UNSUPPORTED = "unsupported"
    # A provider (embedding, reranker or LLM) was unavailable, so we didn't risk an answer.
    PROVIDER_UNAVAILABLE = "provider_unavailable"


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One unanswered question.
class UnansweredQuestion:
    # 🔒 The owning workspace.
    tenant_id: UUID
    # The bot that was asked.
    bot_id: UUID
    # The customer's question (bounded by the adapter).
    question: str
    # The reply language ('en', 'hi', 'bn'...).
    language: str
    # Why it wasn't answered.
    reason: UnansweredReason
    # The best retrieval score, if any.
    top_score: float | None
    # Which published config version was used, if known.
    config_version: int | None
    # The conversation it came from (None outside a chat, e.g. evals).
    conversation_id: UUID | None = None


# Contract: store one unanswered question.
class UnansweredLog(Protocol):
    # Save it (inside the caller's transaction).
    async def record(self, item: UnansweredQuestion) -> None: ...

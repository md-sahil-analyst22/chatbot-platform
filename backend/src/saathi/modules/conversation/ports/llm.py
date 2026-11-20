# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contracts for AI language models (LLMs): send messages, get a reply (or a stream of
#       words).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""LLM ports, split by capability (Interface Segregation).

The model, temperature and token limit are chosen PER REQUEST (from the bot's published
configuration), so one adapter instance can serve every bot that uses the same provider key.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
# One message: who said it (role) and what (content).
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
# The model's reply plus token counts (for cost tracking).
class LLMResponse:
    text: str
    model: str
    tokens_in: int
    tokens_out: int


# Contract: messages in, complete reply out.
class CompletionClient(Protocol):
    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse: ...


# Contract: messages in, reply word-by-word (used from Phase 3).
class StreamingClient(Protocol):
    def stream(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]: ...

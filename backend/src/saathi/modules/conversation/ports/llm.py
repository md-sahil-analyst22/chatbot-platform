# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contracts for AI language models (LLMs): send messages, get a reply (or a stream of
#       words).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""LLM ports, split by capability (Interface Segregation).

The model, temperature and token limit are chosen PER REQUEST (from the bot's published
configuration), so one adapter instance can serve every bot that uses the same provider key.
"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`; Sequence = type for a read-only list.
from collections.abc import AsyncIterator, Sequence

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From typing — type-hint helpers: Literal = only these exact values; Protocol = an interface:
#   any class with these methods fits.
from typing import Literal, Protocol


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# One message: who said it (role) and what (content).
class ChatMessage:
    # Who said it: the customer ('user') or the bot ('assistant').
    role: Literal["user", "assistant"]
    # The text.
    content: str


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# The model's reply plus token counts (for cost tracking).
class LLMResponse:
    # The reply text.
    text: str
    # Which model actually answered.
    model: str
    # Tokens sent (for cost tracking).
    tokens_in: int
    # Tokens received.
    tokens_out: int


# Contract: messages in, complete reply out.
class CompletionClient(Protocol):
    # Ask for one complete reply, given:
    async def complete(
        # self = this object itself (Python passes it in automatically).
        self,
        # Everything after '*' must be passed by name, e.g. api_key=...
        *,
        # our system prompt (built by prompt_builder.py),
        system: str,
        # the conversation so far,
        messages: Sequence[ChatMessage],
        # the vendor's model id,
        model: str,
        # creativity (0-1),
        temperature: float,
        # the longest reply allowed.
        max_tokens: int,
    ) -> LLMResponse: ...


# Contract: messages in, reply word-by-word (used from Phase 3).
class StreamingClient(Protocol):
    # Ask for the reply word by word, given the same inputs:
    def stream(
        # self = this object itself (Python passes it in automatically).
        self,
        # Everything after '*' must be passed by name, e.g. api_key=...
        *,
        # our system prompt (built by prompt_builder.py),
        system: str,
        # the conversation so far,
        messages: Sequence[ChatMessage],
        # the vendor's model id,
        model: str,
        # creativity,
        temperature: float,
        # the longest reply allowed.
        max_tokens: int,
    ) -> AsyncIterator[str]: ...

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: A tiny 'tracer' interface for timing each step of a chat reply.
# Status: 🟡 Only a do-nothing version today; Langfuse plugs in here in Phase 3.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Tracing / cost hooks (Langfuse in P3.9, Sentry in P6.10).

Kept behind a tiny interface so business code calls `tracer.span(...)` without importing the
Langfuse SDK. Every span carries tenant_id, bot_id, conversation_id - never message text with PII.
"""

# From collections.abc — standard type names for collections: Iterator = type for a one-pass
#   loop source.
from collections.abc import Iterator

# From contextlib — helpers for building `with` blocks: contextmanager = turns a function into a
#   `with` block.
from contextlib import contextmanager

# From typing — type-hint helpers: Any = any type; Protocol = an interface: any class with these
#   methods fits.
from typing import Any, Protocol


# The contract: `span(name)` wraps one timed step.
class Tracer(Protocol):
    # span(name) returns a `with` block that times one step; `...` = no body in a contract.
    def span(self, name: str, **attributes: Any) -> Any: ...


# Does nothing - lets the code call the tracer before a real one exists.
class NoopTracer:
    # @contextmanager turns the function below into a `with` block.
    @contextmanager
    # Same signature as the contract, so it can stand in for a real tracer.
    def span(self, name: str, **attributes: Any) -> Iterator[None]:
        # Do nothing; just let the code inside the `with` block run.
        yield None

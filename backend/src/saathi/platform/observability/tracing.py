"""Tracing / cost hooks (Langfuse in P3.9, Sentry in P6.10).

Kept behind a tiny interface so business code calls `tracer.span(...)` without importing the
Langfuse SDK. Every span carries tenant_id, bot_id, conversation_id - never message text with PII.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol


class Tracer(Protocol):
    def span(self, name: str, **attributes: Any) -> Any: ...


class NoopTracer:
    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[None]:
        yield None

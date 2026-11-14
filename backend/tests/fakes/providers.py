"""Deterministic provider fakes. `mode` simulates failures for contract tests."""

import hashlib
from collections.abc import Sequence
from typing import Literal

from saathi.modules.conversation.ports.llm import ChatMessage, LLMResponse
from saathi.modules.knowledge.ports.providers import RerankResult
from saathi.platform.errors import ProviderError, ProviderTimeoutError

Mode = Literal["ok", "error", "timeout"]


def _fail(mode: Mode) -> None:
    if mode == "error":
        raise ProviderError("fake failure")
    if mode == "timeout":
        raise ProviderTimeoutError("fake timeout")


class FakeEmbedder:
    model_name = "fake-embed"

    def __init__(self, mode: Mode = "ok", dimensions: int = 8) -> None:
        self._mode = mode
        self._dim = dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        _fail(self._mode)
        return [[b / 255 for b in hashlib.sha256(t.encode()).digest()[: self._dim]] for t in texts]


class FakeReranker:
    def __init__(self, mode: Mode = "ok") -> None:
        self._mode = mode

    async def rerank(self, query: str, documents: Sequence[str], top_n: int) -> list[RerankResult]:
        if not documents or top_n <= 0:
            return []
        _fail(self._mode)
        words = set(query.lower().split())
        scored = [
            RerankResult(index=i, score=float(len(words & set(d.lower().split()))))
            for i, d in enumerate(documents)
        ]
        return sorted(scored, key=lambda r: r.score, reverse=True)[:top_n]


class FakeCompletionClient:
    def __init__(self, mode: Mode = "ok", reply: str = "fake reply") -> None:
        self._mode = mode
        self._reply = reply

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        _fail(self._mode)
        return LLMResponse(text=self._reply, model=model, tokens_in=1, tokens_out=1)

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every reranker must follow.
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# json — reads and writes JSON text.
import json

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From tests.fakes.providers — fake vendor adapters: FakeReranker = fake reranker; Mode = which
#   failure a fake should simulate.
from tests.fakes.providers import FakeReranker, Mode

# From saathi.modules.knowledge.adapters.rerankers.cohere_reranker — the Cohere reranker:
#   CohereReranker = the Cohere reranker.
from saathi.modules.knowledge.adapters.rerankers.cohere_reranker import CohereReranker

# From saathi.modules.knowledge.ports.providers — parser, embedder and reranker contracts:
#   Reranker = contract: best documents first.
from saathi.modules.knowledge.ports.providers import Reranker

# From saathi.platform.errors — our error types: ProviderError = a vendor failed;
#   ProviderTimeoutError = a vendor was too slow.
from saathi.platform.errors import ProviderError, ProviderTimeoutError

DOCS = ["gst registration documents", "office hours", "itr filing fees", "clinic timings"]


class RerankerContract:
    def make(self, mode: Mode = "ok") -> Reranker:
        raise NotImplementedError

    async def test_at_most_top_n_best_first_valid_indices(self) -> None:
        out = await self.make().rerank("itr fees", DOCS, top_n=2)
        assert len(out) <= 2
        assert [r.score for r in out] == sorted((r.score for r in out), reverse=True)
        assert all(0 <= r.index < len(DOCS) for r in out)

    async def test_empty_documents_returns_empty(self) -> None:
        assert await self.make().rerank("q", [], top_n=5) == []

    async def test_failure_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError):
            await self.make("error").rerank("q", DOCS, top_n=2)

    async def test_timeout_raises_provider_timeout(self) -> None:
        with pytest.raises(ProviderTimeoutError):
            await self.make("timeout").rerank("q", DOCS, top_n=2)


class TestFakeReranker(RerankerContract):
    def make(self, mode: Mode = "ok") -> Reranker:
        return FakeReranker(mode)


class TestCohereReranker(RerankerContract):
    def make(self, mode: Mode = "ok") -> Reranker:
        def handler(request: httpx.Request) -> httpx.Response:
            if mode == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            if mode == "error":
                return httpx.Response(503)
            body = json.loads(request.content)
            n = len(body["documents"])
            # unsorted + one out-of-range index: the adapter must sort and filter
            results = [{"index": i, "relevance_score": 0.1 * i} for i in range(n)]
            results.append({"index": 99, "relevance_score": 0.99})
            return httpx.Response(200, json={"results": results})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return CohereReranker(http, api_key="test")

import json

import httpx
import pytest
from tests.fakes.providers import FakeReranker, Mode

from saathi.modules.knowledge.adapters.rerankers.cohere_reranker import CohereReranker
from saathi.modules.knowledge.ports.providers import Reranker
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

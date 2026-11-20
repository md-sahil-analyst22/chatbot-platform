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

# Four sample documents.
DOCS = ["gst registration documents", "office hours", "itr filing fees", "clinic timings"]


# The rules EVERY reranker must follow (fake and Cohere).
class RerankerContract:
    # Each concrete test class below says which implementation to test by overriding make().
    #   `mode` asks it to work, fail or time out.
    def make(self, mode: Mode = "ok") -> Reranker:
        # The base class itself has no implementation.
        raise NotImplementedError

    # At most top_n results, best first, with valid positions.
    async def test_at_most_top_n_best_first_valid_indices(self) -> None:
        # Rerank for 'itr fees', top 2.
        out = await self.make().rerank("itr fees", DOCS, top_n=2)
        # No more than 2.
        assert len(out) <= 2
        # Sorted by score, highest first.
        assert [r.score for r in out] == sorted((r.score for r in out), reverse=True)
        # Every position points at a real document.
        assert all(0 <= r.index < len(DOCS) for r in out)

    # No documents -> no results (and no vendor call).
    async def test_empty_documents_returns_empty(self) -> None:
        # Must be an empty list.
        assert await self.make().rerank("q", [], top_n=5) == []

    # A vendor failure becomes ProviderError.
    async def test_failure_raises_provider_error(self) -> None:
        # Expect ProviderError from the next line:
        with pytest.raises(ProviderError):
            # rerank in 'error' mode.
            await self.make("error").rerank("q", DOCS, top_n=2)

    # A vendor timeout becomes ProviderTimeoutError.
    async def test_timeout_raises_provider_timeout(self) -> None:
        # Expect ProviderTimeoutError from the next line:
        with pytest.raises(ProviderTimeoutError):
            # rerank in 'timeout' mode.
            await self.make("timeout").rerank("q", DOCS, top_n=2)


# Run the rules against the fake reranker.
class TestFakeReranker(RerankerContract):
    # Which implementation:
    def make(self, mode: Mode = "ok") -> Reranker:
        # the fake.
        return FakeReranker(mode)


# Run the same rules against the real Cohere adapter, with a fake Cohere server.
class TestCohereReranker(RerankerContract):
    # Which implementation:
    def make(self, mode: Mode = "ok") -> Reranker:
        # A fake Cohere server that answers each request:
        def handler(request: httpx.Request) -> httpx.Response:
            # in timeout mode...
            if mode == "timeout":
                # ...raise a timeout;
                raise httpx.ReadTimeout("timeout", request=request)
            # in error mode...
            if mode == "error":
                # ...answer 503;
                return httpx.Response(503)
            # otherwise read the request,
            body = json.loads(request.content)
            # count the documents sent,
            n = len(body["documents"])
            # unsorted + one out-of-range index: the adapter must sort and filter
            results = [{"index": i, "relevance_score": 0.1 * i} for i in range(n)]
            # and add a bogus result pointing past the end (the adapter must drop it),
            results.append({"index": 99, "relevance_score": 0.99})
            # then answer 200 with the results.
            return httpx.Response(200, json={"results": results})

        # An HTTP client wired to the fake server.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # The real Cohere adapter using it.
        return CohereReranker(http, api_key="test")

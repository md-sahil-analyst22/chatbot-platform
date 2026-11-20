# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Re-orders search results by relevance using Cohere (the default reranker, ADR-0006).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Cohere rerank adapter (implements Reranker). Settings: COHERE_*."""

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# httpx — the HTTP client we use to call other web services.
import httpx

# From pydantic — checks data against declared types and rules: SecretStr = text that hides
#   itself when printed or logged.
from pydantic import SecretStr

# From pydantic_settings — reads settings from environment variables and .env: BaseSettings =
#   parent class for a group of settings; SettingsConfigDict = where settings are read from (.env,
#   prefix).
from pydantic_settings import BaseSettings, SettingsConfigDict

# From saathi.modules.knowledge.adapters — parser, embedder and reranker registries:
#   reranker_registry = reranker vendors.
from saathi.modules.knowledge.adapters import reranker_registry

# From saathi.modules.knowledge.ports.providers — parser, embedder and reranker contracts:
#   RerankResult = one reranked result.
from saathi.modules.knowledge.ports.providers import RerankResult

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing;
#   ProviderError = a vendor failed; ProviderTimeoutError = a vendor was too slow.
from saathi.platform.errors import ConfigurationError, ProviderError, ProviderTimeoutError


# COHERE_* settings from .env.
class CohereSettings(BaseSettings):
    # Read COHERE_* variables from .env and ignore the rest.
    model_config = SettingsConfigDict(env_prefix="COHERE_", env_file=".env", extra="ignore")

    # 🔒 COHERE_API_KEY (hidden when printed).
    api_key: SecretStr | None = None
    # COHERE_RERANK_MODEL.
    rerank_model: str = "rerank-v3.5"
    # COHERE_BASE_URL.
    base_url: str = "https://api.cohere.com"
    # COHERE_TIMEOUT_SECONDS (5 s: reranking sits in the chat reply path).
    timeout_seconds: float = 5.0


# The Cohere reranker.
class CohereReranker:
    # Created by create_cohere_reranker() below with:
    def __init__(
        # self = this object itself (Python passes it in automatically).
        self,
        # the shared HTTP client,
        http: httpx.AsyncClient,
        # Everything after '*' must be passed by name, e.g. api_key=...
        *,
        # 🔒 the vendor API key,
        api_key: str,
        # the model,
        model: str = "rerank-v3.5",
        # the API address,
        base_url: str = "https://api.cohere.com",
        # and the time limit.
        timeout_s: float = 5.0,
    ) -> None:
        # Remember the HTTP client.
        self._http = http
        # Remember the model.
        self._model = model
        # The rerank address.
        self._url = f"{base_url.rstrip('/')}/v2/rerank"
        # 🔒 The key travels in the Authorization header.
        self._headers = {"Authorization": f"Bearer {api_key}"}
        # Remember the time limit.
        self._timeout = timeout_s

    # Question + candidate texts -> the best `top_n`, with scores.
    async def rerank(self, query: str, documents: Sequence[str], top_n: int) -> list[RerankResult]:
        # Nothing to rank, or nothing wanted...
        if not documents or top_n <= 0:
            # ...return an empty list without calling Cohere.
            return []
        # Try the call:
        try:
            # POST to Cohere
            r = await self._http.post(
                # at the rerank address,
                self._url,
                # with the key header,
                headers=self._headers,
                # within the time limit,
                timeout=self._timeout,
                # sending JSON:
                json={
                    # the model,
                    "model": self._model,
                    # the question,
                    "query": query,
                    # the candidate texts,
                    "documents": list(documents),
                    # how many to return (never more than we sent).
                    "top_n": min(top_n, len(documents)),
                },
            )
            # An error status counts as a failure.
            r.raise_for_status()
            # Turn each result into a RerankResult (position + score).
            results = [
                RerankResult(index=int(x["index"]), score=float(x["relevance_score"]))
                for x in r.json()["results"]
            ]
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("reranker timed out") from exc
        # Network problem or unexpected answer:
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            # vendor error.
            raise ProviderError("reranker failed") from exc
        # Contract: best first, at most top_n, indices valid.
        results = [x for x in results if 0 <= x.index < len(documents)]
        # Best score first, at most top_n.
        return sorted(results, key=lambda x: x.score, reverse=True)[:top_n]


# Register under the name 'cohere'.
@reranker_registry.register("cohere")
# The factory the registry calls.
def create_cohere_reranker(http: httpx.AsyncClient) -> CohereReranker:
    # Read the COHERE_* settings.
    s = CohereSettings()
    # No key...
    if s.api_key is None:
        # ...refuse to start.
        raise ConfigurationError("COHERE_API_KEY must be set")
    # Build the reranker with:
    return CohereReranker(
        # the HTTP client,
        http,
        # the key,
        api_key=s.api_key.get_secret_value(),
        # the model,
        model=s.rerank_model,
        # the API address,
        base_url=s.base_url,
        # the time limit.
        timeout_s=s.timeout_seconds,
    )

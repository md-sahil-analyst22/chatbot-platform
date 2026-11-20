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
    model_config = SettingsConfigDict(env_prefix="COHERE_", env_file=".env", extra="ignore")

    api_key: SecretStr | None = None
    rerank_model: str = "rerank-v3.5"
    base_url: str = "https://api.cohere.com"
    timeout_seconds: float = 5.0


# The Cohere reranker.
class CohereReranker:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        model: str = "rerank-v3.5",
        base_url: str = "https://api.cohere.com",
        timeout_s: float = 5.0,
    ) -> None:
        self._http = http
        self._model = model
        self._url = f"{base_url.rstrip('/')}/v2/rerank"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._timeout = timeout_s

    # Question + candidate texts -> the best `top_n`, with scores.
    async def rerank(self, query: str, documents: Sequence[str], top_n: int) -> list[RerankResult]:
        if not documents or top_n <= 0:
            return []
        try:
            r = await self._http.post(
                self._url,
                headers=self._headers,
                timeout=self._timeout,
                json={
                    "model": self._model,
                    "query": query,
                    "documents": list(documents),
                    "top_n": min(top_n, len(documents)),
                },
            )
            r.raise_for_status()
            results = [
                RerankResult(index=int(x["index"]), score=float(x["relevance_score"]))
                for x in r.json()["results"]
            ]
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("reranker timed out") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("reranker failed") from exc
        # Contract: best first, at most top_n, indices valid.
        results = [x for x in results if 0 <= x.index < len(documents)]
        return sorted(results, key=lambda x: x.score, reverse=True)[:top_n]


# Register under the name 'cohere'.
@reranker_registry.register("cohere")
def create_cohere_reranker(http: httpx.AsyncClient) -> CohereReranker:
    s = CohereSettings()
    if s.api_key is None:
        raise ConfigurationError("COHERE_API_KEY must be set")
    return CohereReranker(
        http,
        api_key=s.api_key.get_secret_value(),
        model=s.rerank_model,
        base_url=s.base_url,
        timeout_s=s.timeout_seconds,
    )

"""Google Gemini embeddings adapter (implements Embedder). Settings: GEMINI_*.

Platform default (R13, ADR-0006): `gemini-embedding-2` (text input) shortened from 3,072 to 1,536
dimensions (Matryoshka) so pgvector can index it with HNSW. Shortened vectors are not unit length,
so they are L2-normalised here.
"""

import math
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from saathi.modules.knowledge.adapters import embedder_registry
from saathi.platform.errors import ConfigurationError, ProviderError, ProviderTimeoutError

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_BATCH = 100  # batchEmbedContents accepts at most 100 requests per call


class GeminiEmbedderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEMINI_", env_file=".env", extra="ignore")

    api_key: SecretStr | None = None
    embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 1536
    base_url: str = DEFAULT_BASE_URL
    embedding_timeout_seconds: float = 15.0  # separate from the LLM's GEMINI_TIMEOUT_SECONDS


def _l2_normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        raise ProviderError("embedding provider returned a zero vector")
    return [x / norm for x in vector]


class GeminiEmbedder:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        model_name: str = "gemini-embedding-2",
        dimensions: int = 1536,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 15.0,
    ) -> None:
        self.model_name = model_name
        self._dimensions = dimensions
        self._http = http
        self._url = f"{base_url.rstrip('/')}/models/{model_name}:batchEmbedContents"
        self._headers = {"x-goog-api-key": api_key}
        self._timeout = timeout_s

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), MAX_BATCH):
            vectors.extend(await self._embed_batch(texts[start : start + MAX_BATCH]))
        return vectors

    async def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            r = await self._http.post(
                self._url,
                headers=self._headers,
                timeout=self._timeout,
                json={
                    "requests": [
                        {
                            "model": f"models/{self.model_name}",
                            "content": {"parts": [{"text": t}]},
                            "outputDimensionality": self._dimensions,
                        }
                        for t in texts
                    ]
                },
            )
            r.raise_for_status()
            body: dict[str, Any] = r.json()
            raw = [list(map(float, e["values"])) for e in body["embeddings"]]
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("embedding provider timed out") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("embedding provider failed") from exc
        if len(raw) != len(texts):
            raise ProviderError("embedding provider returned the wrong number of vectors")
        if any(len(v) != self._dimensions for v in raw):
            raise ProviderError("embedding provider returned the wrong dimension")
        return [_l2_normalise(v) for v in raw]


@embedder_registry.register("gemini")
def create_gemini_embedder(http: httpx.AsyncClient) -> GeminiEmbedder:
    s = GeminiEmbedderSettings()
    api_key = s.api_key.get_secret_value() if s.api_key else ""
    if not api_key:  # empty counts as missing: fail closed (R16)
        raise ConfigurationError("GEMINI_API_KEY must be set")
    return GeminiEmbedder(
        http,
        api_key=api_key,
        model_name=s.embedding_model,
        dimensions=s.embedding_dimensions,
        base_url=s.base_url,
        timeout_s=s.embedding_timeout_seconds,
    )

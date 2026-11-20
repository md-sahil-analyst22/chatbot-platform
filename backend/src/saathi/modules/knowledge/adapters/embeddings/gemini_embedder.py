# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Turns text into vectors using Google's Gemini embedding model (the platform default,
#       ADR-0006).
# Safety: Checks Gemini's answer: right count, right size (1,536), no empty vectors. Timeouts
#         and errors become clear typed errors.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Google Gemini embeddings adapter (implements Embedder). Settings: GEMINI_*.

Platform default (R13, ADR-0006): `gemini-embedding-2` (text input) shortened from 3,072 to 1,536
dimensions (Matryoshka) so pgvector can index it with HNSW. Shortened vectors are not unit length,
so they are L2-normalised here.
"""

# math — maths functions.
import math

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# From typing — type-hint helpers: Any = any type.
from typing import Any

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
#   embedder_registry = embedder vendors.
from saathi.modules.knowledge.adapters import embedder_registry

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing;
#   ProviderError = a vendor failed; ProviderTimeoutError = a vendor was too slow.
from saathi.platform.errors import ConfigurationError, ProviderError, ProviderTimeoutError

# Google's Gemini API address.
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_BATCH = 100  # batchEmbedContents accepts at most 100 requests per call


# GEMINI_* settings from .env (key, model, size, timeout).
class GeminiEmbedderSettings(BaseSettings):
    # Read GEMINI_* variables from .env and ignore the rest.
    model_config = SettingsConfigDict(env_prefix="GEMINI_", env_file=".env", extra="ignore")

    # 🔒 GEMINI_API_KEY (hidden when printed).
    api_key: SecretStr | None = None
    # GEMINI_EMBEDDING_MODEL (default gemini-embedding-2).
    embedding_model: str = "gemini-embedding-2"
    # GEMINI_EMBEDDING_DIMENSIONS: numbers per vector (1536, platform-wide).
    embedding_dimensions: int = 1536
    # GEMINI_BASE_URL (normally the default).
    base_url: str = DEFAULT_BASE_URL
    embedding_timeout_seconds: float = 15.0  # separate from the LLM's GEMINI_TIMEOUT_SECONDS


# Scale each vector to length 1, so similarity scores are comparable.
def _l2_normalise(vector: list[float]) -> list[float]:
    # The vector's length: square root of the sum of squares.
    norm = math.sqrt(sum(x * x for x in vector))
    # A vector of all zeros can't be scaled...
    if norm == 0:
        # ...so treat it as a vendor error.
        raise ProviderError("embedding provider returned a zero vector")
    # Divide every number by the length, so the vector's length becomes 1.
    return [x / norm for x in vector]


# The Gemini embedder.
class GeminiEmbedder:
    # Created by create_gemini_embedder() below with:
    def __init__(
        # self = this object itself (Python passes it in automatically).
        self,
        # the shared HTTP client,
        http: httpx.AsyncClient,
        # Everything after '*' must be passed by name, e.g. api_key=...
        *,
        # 🔒 the vendor API key,
        api_key: str,
        # the model name,
        model_name: str = "gemini-embedding-2",
        # numbers per vector,
        dimensions: int = 1536,
        # the API address,
        base_url: str = DEFAULT_BASE_URL,
        # and the time limit per call.
        timeout_s: float = 15.0,
    ) -> None:
        # Remember the model name (public: stored with the vectors).
        self.model_name = model_name
        # Remember the vector size.
        self._dimensions = dimensions
        # Remember the HTTP client.
        self._http = http
        # The batch-embedding address for this model.
        self._url = f"{base_url.rstrip('/')}/models/{model_name}:batchEmbedContents"
        # 🔒 The key travels in a header, never in the URL.
        self._headers = {"x-goog-api-key": api_key}
        # Remember the time limit.
        self._timeout = timeout_s

    # Split the texts into batches Gemini accepts and embed each batch.
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        # All vectors, in order.
        vectors: list[list[float]] = []
        # Walk through the texts 100 at a time...
        for start in range(0, len(texts), MAX_BATCH):
            # ...embed each batch and add its vectors.
            vectors.extend(await self._embed_batch(texts[start : start + MAX_BATCH]))
        # Return all vectors.
        return vectors

    # One call to Gemini for one batch.
    async def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        # Try the call:
        try:
            # POST to Gemini
            r = await self._http.post(
                # at the batch address,
                self._url,
                # with the key header,
                headers=self._headers,
                # within the time limit,
                timeout=self._timeout,
                # sending JSON:
                json={
                    # a list of requests,
                    "requests": [
                        # one per text:
                        {
                            # which model,
                            "model": f"models/{self.model_name}",
                            # the text itself,
                            "content": {"parts": [{"text": t}]},
                            # and how many numbers we want back.
                            "outputDimensionality": self._dimensions,
                        }
                        for t in texts
                    ]
                },
            )
            # An error status counts as a failure.
            r.raise_for_status()
            # Read the JSON answer.
            body: dict[str, Any] = r.json()
            # Pull out each vector as a list of floats.
            raw = [list(map(float, e["values"])) for e in body["embeddings"]]
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("embedding provider timed out") from exc
        # Network problem or an unexpected answer shape:
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            # vendor error.
            raise ProviderError("embedding provider failed") from exc
        # Never trust the answer blindly: count and size must match.
        if len(raw) != len(texts):
            # Wrong count -> vendor error.
            raise ProviderError("embedding provider returned the wrong number of vectors")
        # Any vector of the wrong size...
        if any(len(v) != self._dimensions for v in raw):
            # ...-> vendor error.
            raise ProviderError("embedding provider returned the wrong dimension")
        # Scale every vector to length 1 and return them.
        return [_l2_normalise(v) for v in raw]


# Register under the name 'gemini' (EMBEDDING_PROVIDER=gemini).
@embedder_registry.register("gemini")
# The factory the registry calls.
def create_gemini_embedder(http: httpx.AsyncClient) -> GeminiEmbedder:
    # Read the GEMINI_* settings.
    s = GeminiEmbedderSettings()
    # The key as plain text (empty if missing).
    api_key = s.api_key.get_secret_value() if s.api_key else ""
    if not api_key:  # empty counts as missing: fail closed (R16)
        # Refuse to start without it.
        raise ConfigurationError("GEMINI_API_KEY must be set")
    # Build the embedder with:
    return GeminiEmbedder(
        # the HTTP client,
        http,
        # the key,
        api_key=api_key,
        # the model,
        model_name=s.embedding_model,
        # the vector size,
        dimensions=s.embedding_dimensions,
        # the API address,
        base_url=s.base_url,
        # the time limit.
        timeout_s=s.embedding_timeout_seconds,
    )

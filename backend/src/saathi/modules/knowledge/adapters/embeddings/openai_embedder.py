# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Alternative embedder using OpenAI (only used if EMBEDDING_PROVIDER=openai).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""OpenAI embeddings adapter (implements Embedder). Settings: OPENAI_*."""

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
#   embedder_registry = embedder vendors.
from saathi.modules.knowledge.adapters import embedder_registry

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing;
#   ProviderError = a vendor failed; ProviderTimeoutError = a vendor was too slow.
from saathi.platform.errors import ConfigurationError, ProviderError, ProviderTimeoutError


# OPENAI_* settings from .env.
class OpenAIEmbedderSettings(BaseSettings):
    # Read OPENAI_* variables from .env and ignore the rest.
    model_config = SettingsConfigDict(env_prefix="OPENAI_", env_file=".env", extra="ignore")

    # 🔒 OPENAI_API_KEY (hidden when printed).
    api_key: SecretStr | None = None
    # OPENAI_EMBEDDING_MODEL.
    embedding_model: str = "text-embedding-3-small"
    # OPENAI_BASE_URL.
    base_url: str = "https://api.openai.com/v1"
    # OPENAI_TIMEOUT_SECONDS.
    timeout_seconds: float = 15.0


# The OpenAI embedder.
class OpenAIEmbedder:
    # Created by create_openai_embedder() below with:
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
        model_name: str,
        # the API address,
        base_url: str = "https://api.openai.com/v1",
        # and the time limit.
        timeout_s: float = 15.0,
    ) -> None:
        # Remember the model name.
        self.model_name = model_name
        # Remember the HTTP client.
        self._http = http
        # The embeddings address.
        self._url = f"{base_url.rstrip('/')}/embeddings"
        # 🔒 The key travels in the Authorization header.
        self._headers = {"Authorization": f"Bearer {api_key}"}
        # Remember the time limit.
        self._timeout = timeout_s

    # Send texts, get vectors back.
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        # Nothing to embed...
        if not texts:
            # ...so return an empty list without calling OpenAI.
            return []
        # Try the call:
        try:
            # POST to OpenAI
            r = await self._http.post(
                # at the embeddings address,
                self._url,
                # with the key header,
                headers=self._headers,
                # within the time limit,
                timeout=self._timeout,
                # sending the model and the texts.
                json={"model": self.model_name, "input": list(texts)},
            )
            # An error status counts as a failure.
            r.raise_for_status()
            # Put the results back in the order the texts were sent.
            data = sorted(r.json()["data"], key=lambda d: d["index"])
            # Pull out each vector as a list of floats.
            vectors = [list(map(float, d["embedding"])) for d in data]
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("embedding provider timed out") from exc
        # Network problem or unexpected answer:
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            # vendor error.
            raise ProviderError("embedding provider failed") from exc
        # Wrong number of vectors...
        if len(vectors) != len(texts):
            # ...-> vendor error.
            raise ProviderError("embedding provider returned the wrong number of vectors")
        # Return the vectors.
        return vectors


# Register under the name 'openai'.
@embedder_registry.register("openai")
# The factory the registry calls.
def create_openai_embedder(http: httpx.AsyncClient) -> OpenAIEmbedder:
    # Read the OPENAI_* settings.
    s = OpenAIEmbedderSettings()
    # No key...
    if s.api_key is None:
        # ...refuse to start.
        raise ConfigurationError("OPENAI_API_KEY must be set")
    # Build the embedder with:
    return OpenAIEmbedder(
        # the HTTP client,
        http,
        # the key,
        api_key=s.api_key.get_secret_value(),
        # the model,
        model_name=s.embedding_model,
        # the API address,
        base_url=s.base_url,
        # the time limit.
        timeout_s=s.timeout_seconds,
    )

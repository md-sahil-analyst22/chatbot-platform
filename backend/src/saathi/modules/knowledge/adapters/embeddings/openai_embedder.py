"""OpenAI embeddings adapter (implements Embedder). Settings: OPENAI_*."""

from collections.abc import Sequence

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from saathi.modules.knowledge.adapters import embedder_registry
from saathi.platform.errors import ConfigurationError, ProviderError, ProviderTimeoutError


class OpenAIEmbedderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENAI_", env_file=".env", extra="ignore")

    api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-3-small"
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 15.0


class OpenAIEmbedder:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        model_name: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 15.0,
    ) -> None:
        self.model_name = model_name
        self._http = http
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._timeout = timeout_s

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            r = await self._http.post(
                self._url,
                headers=self._headers,
                timeout=self._timeout,
                json={"model": self.model_name, "input": list(texts)},
            )
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda d: d["index"])
            vectors = [list(map(float, d["embedding"])) for d in data]
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("embedding provider timed out") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("embedding provider failed") from exc
        if len(vectors) != len(texts):
            raise ProviderError("embedding provider returned the wrong number of vectors")
        return vectors


@embedder_registry.register("openai")
def create_openai_embedder(http: httpx.AsyncClient) -> OpenAIEmbedder:
    s = OpenAIEmbedderSettings()
    if s.api_key is None:
        raise ConfigurationError("OPENAI_API_KEY must be set")
    return OpenAIEmbedder(
        http,
        api_key=s.api_key.get_secret_value(),
        model_name=s.embedding_model,
        base_url=s.base_url,
        timeout_s=s.timeout_seconds,
    )

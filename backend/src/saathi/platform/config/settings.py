"""Core settings: infrastructure + which provider to use.

Provider-specific settings (API keys, model names) live next to each adapter, e.g.
`AnthropicSettings` reads ANTHROPIC_*. Adding a vendor never edits this file (Open/Closed).
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["local", "test", "staging", "production"] = "local"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = []

    database_url: SecretStr
    redis_url: SecretStr

    auth_jwks_url: str | None = None
    auth_issuer: str | None = None
    auth_audience: str | None = None

    # Platform-wide registry keys. The LLM is chosen PER BOT via the model catalog
    # (platform/config/model_catalog.py). Embeddings stay platform-wide because changing the
    # embedding model requires re-indexing every document.
    embedding_provider: str = "openai"
    reranker_provider: str = "cohere"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # required values come from the environment

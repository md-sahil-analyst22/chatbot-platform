# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The core settings of the app, read from the .env file (or the server's environment).
# Examples: ENV (local/production), DATABASE_URL, REDIS_URL, AUTH_* (login), and which vendor to
#           use for embeddings, reranking, speech and storage.
# Rule: Only core settings live here. Each vendor keeps its own settings next to its adapter
#       (e.g. GeminiSettings), so adding a vendor never edits this file (R12).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Core settings: infrastructure + which provider to use.

Provider-specific settings (API keys, model names) live next to each adapter, e.g.
`AnthropicSettings` reads ANTHROPIC_*. Adding a vendor never edits this file (Open/Closed).
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Each field = one setting. pydantic reads the matching environment variable (upper-case name)
# and checks its type.
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["local", "test", "staging", "production"] = "local"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = []

    # 🔒 SecretStr hides the value when printed or logged, so passwords never leak.
    database_url: SecretStr
    redis_url: SecretStr

    # Login settings (ADR-0007). All three empty = no login checker = every /api/v1 call
    # refused.
    auth_jwks_url: str | None = None
    auth_issuer: str | None = None
    auth_audience: str | None = None

    # Platform-wide registry keys. The LLM is chosen PER BOT via the model catalog
    # (platform/config/model_catalog.py). Embeddings stay platform-wide because changing the
    # embedding model requires re-indexing every document (R13, ADR-0006).
    # Vendor names looked up in the registries (bootstrap/providers.py).
    embedding_provider: str = "gemini"
    reranker_provider: str = "cohere"
    stt_provider: str = "sarvam"
    tts_provider: str = "sarvam"
    storage_provider: str = "supabase"


# Read the settings once and reuse them (lru_cache remembers the result).
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # required values come from the environment

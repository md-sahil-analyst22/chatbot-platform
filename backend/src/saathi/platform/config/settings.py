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

# From functools — tools for working with functions: lru_cache = remembers a function's result
#   so the work runs once.
from functools import lru_cache

# From typing — type-hint helpers: Literal = only these exact values.
from typing import Literal

# From pydantic — checks data against declared types and rules: SecretStr = text that hides
#   itself when printed or logged.
from pydantic import SecretStr

# From pydantic_settings — reads settings from environment variables and .env: BaseSettings =
#   parent class for a group of settings; SettingsConfigDict = where settings are read from (.env,
#   prefix).
from pydantic_settings import BaseSettings, SettingsConfigDict


# Each field = one setting. pydantic reads the matching environment variable (upper-case name)
# and checks its type.
class Settings(BaseSettings):
    # Read from the .env file (UTF-8); ignore any variables this class doesn't know.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ENV: which environment this is (default 'local').
    env: Literal["local", "test", "staging", "production"] = "local"
    # APP_VERSION: shown in the API docs.
    app_version: str = "0.1.0"
    # LOG_LEVEL: how detailed the logs are (DEBUG, INFO, WARNING...).
    log_level: str = "INFO"
    # CORS_ALLOWED_ORIGINS: websites whose browsers may call the API (none by default).
    cors_allowed_origins: list[str] = []

    # 🔒 SecretStr hides the value when printed or logged, so passwords never leak.
    database_url: SecretStr
    # REDIS_URL: where Redis lives (also secret: may contain a password).
    redis_url: SecretStr

    # Login settings (ADR-0007). All three empty = no login checker = every /api/v1 call
    # refused.
    auth_jwks_url: str | None = None
    # AUTH_ISSUER: who must have issued login tokens (our Supabase project).
    auth_issuer: str | None = None
    # AUTH_AUDIENCE: who login tokens must be meant for ('authenticated').
    auth_audience: str | None = None

    # Platform-wide registry keys. The LLM is chosen PER BOT via the model catalog
    # (platform/config/model_catalog.py). Embeddings stay platform-wide because changing the
    # embedding model requires re-indexing every document (R13, ADR-0006).
    # Vendor names looked up in the registries (bootstrap/providers.py).
    embedding_provider: str = "gemini"
    # RERANKER_PROVIDER: which reranker vendor to use.
    reranker_provider: str = "cohere"
    # STT_PROVIDER: which speech-to-text vendor to use.
    stt_provider: str = "sarvam"
    # TTS_PROVIDER: which text-to-speech vendor to use.
    tts_provider: str = "sarvam"
    # STORAGE_PROVIDER: which file storage vendor to use.
    storage_provider: str = "supabase"
    # CRAWLER_PROVIDER: which website crawler to use (Phase 2).
    crawler_provider: str = "http"


# Read the settings once and reuse them (lru_cache remembers the result).
@lru_cache(maxsize=1)
# Returns the app's settings (the decorator above makes it read .env only once).
def get_settings() -> Settings:
    return Settings()  # required values come from the environment

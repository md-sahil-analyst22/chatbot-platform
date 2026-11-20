# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Hands out the API key to use for an AI provider (e.g. Gemini).
# Today: Every tenant uses Saathi's own platform keys from .env.
# Phase 8: Tenants on the Pro plan can bring their own keys; this is where that will be plugged
#          in.
# Security: 🔒 Keys are read from settings as hidden values and never printed.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Credential sources (composition root).

Phases 1-7: every tenant uses the platform's own provider keys.
Phase 8 (Pro): wrap with the tenant vault (modules/credentials): tenant key first, then the
platform key only if the tenant's plan allows a fallback.
"""

# From collections.abc — standard type names for collections: Mapping = type for a read-only
#   dictionary.
from collections.abc import Mapping

# From pydantic — checks data against declared types and rules: SecretStr = text that hides
#   itself when printed or logged.
from pydantic import SecretStr

# From saathi.modules.conversation.adapters.llm.anthropic_llm — the Anthropic Claude adapter:
#   AnthropicSettings = ANTHROPIC_* settings.
from saathi.modules.conversation.adapters.llm.anthropic_llm import AnthropicSettings

# From saathi.modules.conversation.adapters.llm.gemini_llm — the Google Gemini adapter:
#   GeminiSettings = GEMINI_* settings.
from saathi.modules.conversation.adapters.llm.gemini_llm import GeminiSettings


# Unwrap a hidden secret value (or return None if it isn't set).
def _reveal(secret: SecretStr | None) -> str | None:
    return secret.get_secret_value() if secret else None


# Holds the platform's keys per provider name.
class PlatformCredentialSource:
    def __init__(self, keys: Mapping[str, str | None]) -> None:
        # Drop empty keys, so an unset key counts as 'no key' (fail closed).
        self._keys = {provider: key for provider, key in keys.items() if key}

    # 'Which key should tenant X use for provider Y?' Today: the platform key.
    async def api_key_for(self, tenant_id: str, provider: str) -> str | None:
        return self._keys.get(provider)


# Build the source from the keys in .env - one line per AI provider.
def platform_credentials_from_env() -> PlatformCredentialSource:
    # One line per LLM provider adapter.
    return PlatformCredentialSource(
        {
            "gemini": _reveal(GeminiSettings().api_key),
            "anthropic": _reveal(AnthropicSettings().api_key),
        }
    )

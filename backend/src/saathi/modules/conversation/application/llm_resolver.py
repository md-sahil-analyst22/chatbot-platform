# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Picks the AI model for a bot and creates a ready client for it, with the right API key.
# Security: 🔒 No key -> stop with an error. Never fall back to another key.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Per-bot model resolution: catalog key + bot settings -> a ready CompletionClient."""

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From saathi.modules.conversation.ports.credentials — contract for getting a vendor API key:
#   CredentialSource = contract: give me the API key.
from saathi.modules.conversation.ports.credentials import CredentialSource

# From saathi.modules.conversation.ports.llm — AI language-model contracts: CompletionClient =
#   contract: messages in, reply out.
from saathi.modules.conversation.ports.llm import CompletionClient

# From saathi.platform.config.model_catalog — the list of AI models tenants may choose:
#   ModelCatalog = the catalog.
from saathi.platform.config.model_catalog import ModelCatalog

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing.
from saathi.platform.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
# Which vendor, which model, and its limits.
class ModelSelection:
    provider: str
    model_id: str
    temperature: float
    max_output_tokens: int


# Catalog key (e.g. 'standard') -> real vendor + model; output length capped by the catalog.
def select_model(
    catalog: ModelCatalog, model_key: str, *, temperature: float, max_output_tokens: int
) -> ModelSelection:
    option = catalog.get(model_key)
    return ModelSelection(
        provider=option.provider,
        model_id=option.model_id,
        temperature=temperature,
        max_output_tokens=min(max_output_tokens, option.max_output_tokens),
    )


# Contract: (vendor, key) -> client.
class CompletionClientFactory(Protocol):
    def __call__(self, provider: str, api_key: str) -> CompletionClient: ...


# Combines the key source and the client factory.
class LlmResolver:
    def __init__(self, factory: CompletionClientFactory, credentials: CredentialSource) -> None:
        self._factory = factory
        self._credentials = credentials

    # Find the key for this tenant + vendor, then build the client.
    async def resolve(self, tenant_id: str, selection: ModelSelection) -> CompletionClient:
        api_key = await self._credentials.api_key_for(tenant_id, selection.provider)
        if not api_key:
            # Fail closed: never fall back to another tenant's or an unintended key.
            raise ConfigurationError(f"no API key available for provider '{selection.provider}'")
        return self._factory(selection.provider, api_key)

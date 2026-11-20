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


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# Which vendor, which model, and its limits.
class ModelSelection:
    # The vendor name (registry key), e.g. 'gemini'.
    provider: str
    # The vendor's model id.
    model_id: str
    # Creativity (0-1).
    temperature: float
    # The longest reply allowed.
    max_output_tokens: int


# Catalog key (e.g. 'standard') -> real vendor + model; output length capped by the catalog.
def select_model(
    catalog: ModelCatalog, model_key: str, *, temperature: float, max_output_tokens: int
) -> ModelSelection:
    # Look the key up in the catalog (422 if unknown).
    option = catalog.get(model_key)
    # Build the selection:
    return ModelSelection(
        # vendor from the catalog,
        provider=option.provider,
        # model id from the catalog,
        model_id=option.model_id,
        # the bot's temperature,
        temperature=temperature,
        # the bot's limit, but never above the catalog's limit.
        max_output_tokens=min(max_output_tokens, option.max_output_tokens),
    )


# Contract: (vendor, key) -> client.
class CompletionClientFactory(Protocol):
    # Calling the factory with (vendor, key) returns a ready client.
    def __call__(self, provider: str, api_key: str) -> CompletionClient: ...


# Combines the key source and the client factory.
class LlmResolver:
    # Needs a client factory and a key source.
    def __init__(self, factory: CompletionClientFactory, credentials: CredentialSource) -> None:
        # Remember the factory.
        self._factory = factory
        # Remember the key source.
        self._credentials = credentials

    # Find the key for this tenant + vendor, then build the client.
    async def resolve(self, tenant_id: str, selection: ModelSelection) -> CompletionClient:
        # Ask for the key for this tenant + vendor.
        api_key = await self._credentials.api_key_for(tenant_id, selection.provider)
        # No key:
        if not api_key:
            # Fail closed: never fall back to another tenant's or an unintended key.
            raise ConfigurationError(f"no API key available for provider '{selection.provider}'")
        # Build the client with that key.
        return self._factory(selection.provider, api_key)

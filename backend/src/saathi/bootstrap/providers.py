"""Explicit provider wiring (composition root).

Importing an adapter module runs its @registry.register(...) decorator. Listing the imports here
makes registration explicit and visible - registries are never silently empty.

- LLM: chosen PER BOT (model catalog key in the bot's published config) -> build_llm_resolver().
- Embeddings / reranker / parser: platform-wide (EMBEDDING_PROVIDER, RERANKER_PROVIDER).
"""

import httpx

# --- adapter registrations (one line per vendor) -------------------------------------------
from saathi.bootstrap.credentials import platform_credentials_from_env
from saathi.modules.conversation.adapters import completion_registry
from saathi.modules.conversation.adapters.llm import anthropic_llm  # noqa: F401
from saathi.modules.conversation.application.llm_resolver import LlmResolver
from saathi.modules.conversation.ports.credentials import CredentialSource
from saathi.modules.conversation.ports.llm import CompletionClient
from saathi.modules.knowledge.adapters import (
    embedder_registry,
    parser_registry,
    reranker_registry,
)
from saathi.modules.knowledge.adapters.embeddings import openai_embedder  # noqa: F401
from saathi.modules.knowledge.adapters.parsers import pymupdf_parser  # noqa: F401
from saathi.modules.knowledge.adapters.rerankers import cohere_reranker  # noqa: F401
from saathi.modules.knowledge.ports.providers import DocumentParser, Embedder, Reranker
from saathi.platform.config.settings import Settings


def build_llm_resolver(
    http: httpx.AsyncClient, credentials: CredentialSource | None = None
) -> LlmResolver:
    def factory(provider: str, api_key: str) -> CompletionClient:
        return completion_registry.create(provider, http=http, api_key=api_key)

    return LlmResolver(factory, credentials or platform_credentials_from_env())


def build_embedder(settings: Settings, http: httpx.AsyncClient) -> Embedder:
    return embedder_registry.create(settings.embedding_provider, http=http)


def build_reranker(settings: Settings, http: httpx.AsyncClient) -> Reranker:
    return reranker_registry.create(settings.reranker_provider, http=http)


def build_parser(name: str) -> DocumentParser:
    return parser_registry.create(name)

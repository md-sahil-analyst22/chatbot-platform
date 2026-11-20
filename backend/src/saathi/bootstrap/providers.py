# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Picks WHICH vendor does each job (Gemini, Cohere, Sarvam, Supabase...) based on the
#       settings.
# How: Each vendor adapter registers itself in a 'registry' (a phone book) when imported. The
#      import lines below make that happen; the build_* functions then look a vendor up by the
#      name in .env.
# Why: Switching vendors = changing one setting, not rewriting business code (rule R7).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Explicit provider wiring (composition root).

Importing an adapter module runs its @registry.register(...) decorator. Listing the imports here
makes registration explicit and visible - registries are never silently empty.

- LLM: chosen PER BOT (model catalog key in the bot's published config) -> build_llm_resolver().
- Embeddings / reranker / parser: platform-wide (EMBEDDING_PROVIDER, RERANKER_PROVIDER).
- Speech: platform-wide (STT_PROVIDER, TTS_PROVIDER).
- Object storage: platform-wide (STORAGE_PROVIDER), one private and one public bucket.
"""

from typing import Literal

import httpx

# --- adapter registrations (one line per vendor) -------------------------------------------
# Everything below this line is an import whose main purpose is to register adapters.
from saathi.bootstrap.credentials import platform_credentials_from_env
from saathi.modules.channels.adapters import stt_registry, tts_registry
from saathi.modules.channels.adapters.speech import sarvam_speech  # noqa: F401
from saathi.modules.channels.ports.speech import SpeechToText, TextToSpeech
from saathi.modules.conversation.adapters import completion_registry
from saathi.modules.conversation.adapters.llm import anthropic_llm, gemini_llm  # noqa: F401
from saathi.modules.conversation.application.llm_resolver import LlmResolver
from saathi.modules.conversation.ports.credentials import CredentialSource
from saathi.modules.conversation.ports.llm import CompletionClient
from saathi.modules.knowledge.adapters import (
    embedder_registry,
    parser_registry,
    reranker_registry,
)
from saathi.modules.knowledge.adapters.embeddings import (  # noqa: F401
    gemini_embedder,
    openai_embedder,
)
from saathi.modules.knowledge.adapters.parsers import pymupdf_parser  # noqa: F401
from saathi.modules.knowledge.adapters.rerankers import cohere_reranker  # noqa: F401
from saathi.modules.knowledge.ports.providers import DocumentParser, Embedder, Reranker
from saathi.platform.config.settings import Settings
from saathi.platform.storage import (  # noqa: F401  (supabase_store registers itself)
    ObjectStore,
    object_store_registry,
    supabase_store,
)


# Builds the helper that, per bot, picks the AI model and the right API key.
def build_llm_resolver(
    http: httpx.AsyncClient, credentials: CredentialSource | None = None
) -> LlmResolver:
    # Given a provider name ('gemini') and a key, create that vendor's chat client.
    def factory(provider: str, api_key: str) -> CompletionClient:
        return completion_registry.create(provider, http=http, api_key=api_key)

    return LlmResolver(factory, credentials or platform_credentials_from_env())


# The vendor that turns text into numbers for search (default 'gemini', EMBEDDING_PROVIDER).
def build_embedder(settings: Settings, http: httpx.AsyncClient) -> Embedder:
    return embedder_registry.create(settings.embedding_provider, http=http)


# The vendor that re-sorts search results by relevance (default 'cohere').
def build_reranker(settings: Settings, http: httpx.AsyncClient) -> Reranker:
    return reranker_registry.create(settings.reranker_provider, http=http)


# Reads documents (e.g. 'pymupdf' for PDFs).
def build_parser(name: str) -> DocumentParser:
    return parser_registry.create(name)


# Speech-to-text vendor (default 'sarvam', STT_PROVIDER).
def build_stt(settings: Settings, http: httpx.AsyncClient) -> SpeechToText:
    return stt_registry.create(settings.stt_provider, http=http)


# Text-to-speech vendor (default 'sarvam', TTS_PROVIDER).
def build_tts(settings: Settings, http: httpx.AsyncClient) -> TextToSpeech:
    return tts_registry.create(settings.tts_provider, http=http)


# File storage (default 'supabase'): 'private' bucket for documents, 'public' for logos.
def build_object_store(
    settings: Settings, http: httpx.AsyncClient, visibility: Literal["private", "public"]
) -> ObjectStore:
    return object_store_registry.create(settings.storage_provider, http=http, visibility=visibility)

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

# From typing — type-hint helpers: Literal = only these exact values.
from typing import Literal

# httpx — the HTTP client we use to call other web services.
import httpx

# --- adapter registrations (one line per vendor) -------------------------------------------
# Everything below this line is an import whose main purpose is to register adapters.
# From saathi.bootstrap.credentials — where the platform's own vendor API keys come from:
#   platform_credentials_from_env = reads those keys from .env.
from saathi.bootstrap.credentials import platform_credentials_from_env

# From saathi.modules.channels.adapters — speech vendor registries: stt_registry =
#   speech-to-text vendors; tts_registry = text-to-speech vendors.
from saathi.modules.channels.adapters import stt_registry, tts_registry

# From saathi.modules.channels.adapters.speech — speech vendor adapters: sarvam_speech = the
#   Sarvam adapter module (importing it registers it).
from saathi.modules.channels.adapters.speech import sarvam_speech  # noqa: F401

# From saathi.modules.channels.ports.speech — speech contracts: SpeechToText = speech-to-text
#   contract; TextToSpeech = text-to-speech contract.
from saathi.modules.channels.ports.speech import SpeechToText, TextToSpeech

# From saathi.modules.conversation.adapters — the AI language-model registry:
#   completion_registry = the AI language-model registry.
from saathi.modules.conversation.adapters import completion_registry

# From saathi.modules.conversation.adapters.llm — AI language-model adapters: anthropic_llm =
#   the Claude adapter module (importing it registers it); gemini_llm = the Gemini adapter module
#   (importing it registers it).
from saathi.modules.conversation.adapters.llm import anthropic_llm, gemini_llm  # noqa: F401

# From saathi.modules.conversation.application.llm_resolver — picks the AI model and key for a
#   bot: LlmResolver = finds the key and builds the model client.
from saathi.modules.conversation.application.llm_resolver import LlmResolver

# From saathi.modules.conversation.ports.credentials — contract for getting a vendor API key:
#   CredentialSource = contract: give me the API key.
from saathi.modules.conversation.ports.credentials import CredentialSource

# From saathi.modules.conversation.ports.llm — AI language-model contracts: CompletionClient =
#   contract: messages in, reply out.
from saathi.modules.conversation.ports.llm import CompletionClient

# From saathi.modules.knowledge.adapters — parser, embedder and reranker registries:
#   embedder_registry = embedder vendors; parser_registry = document parsers; reranker_registry =
#   reranker vendors.
from saathi.modules.knowledge.adapters import (
    embedder_registry,
    parser_registry,
    reranker_registry,
)

# From saathi.modules.knowledge.adapters.embeddings — embedder adapters: gemini_embedder = the
#   Gemini embedder module (importing it registers it); openai_embedder = the OpenAI embedder
#   module (importing it registers it).
from saathi.modules.knowledge.adapters.embeddings import (  # noqa: F401
    gemini_embedder,
    openai_embedder,
)

# From saathi.modules.knowledge.adapters.parsers — document parser adapters: pymupdf_parser =
#   the PDF parser module (importing it registers it).
from saathi.modules.knowledge.adapters.parsers import pymupdf_parser  # noqa: F401

# From saathi.modules.knowledge.adapters.rerankers — reranker adapters: cohere_reranker = the
#   Cohere module (importing it registers it).
from saathi.modules.knowledge.adapters.rerankers import cohere_reranker  # noqa: F401

# From saathi.modules.knowledge.ports.providers — parser, embedder and reranker contracts:
#   DocumentParser = contract: file -> text; Embedder = contract: text -> vectors; Reranker =
#   contract: best documents first.
from saathi.modules.knowledge.ports.providers import DocumentParser, Embedder, Reranker

# From saathi.platform.config.settings — the app's core settings: Settings = the settings class.
from saathi.platform.config.settings import Settings

# From saathi.platform.storage — file storage contract and registry: ObjectStore = the file
#   storage contract; object_store_registry = file storage vendors; supabase_store = the Supabase
#   storage module (importing it registers it).
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

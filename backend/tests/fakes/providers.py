# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Fake AI/vendor adapters with predictable answers; `mode` can simulate timeouts and
#       errors.
# How to run: Used automatically by the tests; nothing to run directly.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Deterministic provider fakes. `mode` simulates failures for contract tests."""

# hashlib — fingerprints (hashes) such as SHA-256.
import hashlib

# re — regular expressions (text patterns).
import re

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# From typing — type-hint helpers: Literal = only these exact values.
from typing import Literal

# From saathi.modules.channels.ports.speech — speech contracts: SynthesizedSpeech = generated
#   audio; Transcript = text heard in audio.
from saathi.modules.channels.ports.speech import SynthesizedSpeech, Transcript

# From saathi.modules.conversation.ports.llm — AI language-model contracts: ChatMessage = one
#   chat message; LLMResponse = the model's reply and token counts.
from saathi.modules.conversation.ports.llm import ChatMessage, LLMResponse

# From saathi.modules.knowledge.ports.providers — parser, embedder and reranker contracts:
#   RerankResult = one reranked result.
from saathi.modules.knowledge.ports.providers import RerankResult

# From saathi.platform.errors — our error types: NotFoundError = 404 not found; ProviderError =
#   a vendor failed; ProviderTimeoutError = a vendor was too slow; ValidationError = 422 invalid
#   input.
from saathi.platform.errors import (
    NotFoundError,
    ProviderError,
    ProviderTimeoutError,
    ValidationError,
)

Mode = Literal["ok", "error", "timeout"]


def _fail(mode: Mode) -> None:
    if mode == "error":
        raise ProviderError("fake failure")
    if mode == "timeout":
        raise ProviderTimeoutError("fake timeout")


class FakeEmbedder:
    model_name = "fake-embed"

    def __init__(self, mode: Mode = "ok", dimensions: int = 8) -> None:
        self._mode = mode
        self._dim = dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        _fail(self._mode)
        return [[b / 255 for b in hashlib.sha256(t.encode()).digest()[: self._dim]] for t in texts]


class FakeReranker:
    def __init__(self, mode: Mode = "ok") -> None:
        self._mode = mode

    async def rerank(self, query: str, documents: Sequence[str], top_n: int) -> list[RerankResult]:
        if not documents or top_n <= 0:
            return []
        _fail(self._mode)
        words = set(query.lower().split())
        scored = [
            RerankResult(index=i, score=float(len(words & set(d.lower().split()))))
            for i, d in enumerate(documents)
        ]
        return sorted(scored, key=lambda r: r.score, reverse=True)[:top_n]


class FakeCompletionClient:
    def __init__(self, mode: Mode = "ok", reply: str = "fake reply") -> None:
        self._mode = mode
        self._reply = reply

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        _fail(self._mode)
        return LLMResponse(text=self._reply, model=model, tokens_in=1, tokens_out=1)


class FakeSpeechToText:
    """Returns the audio bytes decoded as text, so tests can control the transcript."""

    def __init__(self, mode: Mode = "ok") -> None:
        self._mode = mode

    async def transcribe(
        self, audio: bytes, *, content_type: str, language: str | None = None
    ) -> Transcript:
        if not audio:
            raise ValidationError("audio is empty")
        _fail(self._mode)
        return Transcript(text=audio.decode(errors="replace"), language=language or "en-IN")


class FakeTextToSpeech:
    def __init__(self, mode: Mode = "ok") -> None:
        self._mode = mode

    async def synthesize(
        self, text: str, *, language: str, voice: str | None = None
    ) -> SynthesizedSpeech:
        if not text.strip():
            raise ValidationError("text is empty")
        _fail(self._mode)
        return SynthesizedSpeech(audio=f"{language}:{text}".encode(), content_type="audio/wav")


_SEGMENT = r"[A-Za-z0-9_\-][A-Za-z0-9_.\-]{0,199}"
_STORAGE_KEY = re.compile(rf"t/{_SEGMENT}(/{_SEGMENT})+")  # same rule as the real adapter


class InMemoryObjectStore:
    def __init__(self, *, public: bool = False) -> None:
        self._public = public
        self._objects: dict[str, tuple[bytes, str]] = {}

    @staticmethod
    def _check(key: str) -> str:
        if not _STORAGE_KEY.fullmatch(key):
            raise ValidationError("invalid storage key")
        return key

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self._objects[self._check(key)] = (data, content_type)

    async def get(self, key: str) -> bytes:
        try:
            return self._objects[self._check(key)][0]
        except KeyError:
            raise NotFoundError("object not found") from None

    async def delete(self, key: str) -> None:
        self._objects.pop(self._check(key), None)

    def public_url(self, key: str) -> str | None:
        return f"memory://public/{self._check(key)}" if self._public else None

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
from saathi.modules.knowledge.ports.providers import EmbedTask, RerankResult

# From saathi.platform.errors — our error types: NotFoundError = 404 not found; ProviderError =
#   a vendor failed; ProviderTimeoutError = a vendor was too slow; ValidationError = 422 invalid
#   input.
from saathi.platform.errors import (
    NotFoundError,
    ProviderError,
    ProviderRejectedError,
    ProviderTimeoutError,
    ValidationError,
)

# How a fake should behave: work normally, fail, or time out.
Mode = Literal["ok", "error", "timeout", "rejected"]


# Make a fake fail on purpose, depending on its mode.
def _fail(mode: Mode) -> None:
    # 'error' mode...
    if mode == "error":
        # ...raises a vendor error.
        raise ProviderError("fake failure")
    # 'timeout' mode...
    if mode == "timeout":
        # ...raises a timeout error.
        raise ProviderTimeoutError("fake timeout")
    # 'rejected' mode...
    if mode == "rejected":
        # ...raises a permanent refusal (like a 403 for unpaid billing).
        raise ProviderRejectedError("fake refusal")


# A fake embedder: same input always gives the same vector, no internet needed.
class FakeEmbedder:
    # Its model name.
    model_name = "fake-embed"

    # Choose the mode and the vector size (8 numbers by default).
    def __init__(self, mode: Mode = "ok", dimensions: int = 8) -> None:
        # Remember the mode.
        self._mode = mode
        # Remember the size.
        self._dim = dimensions

    # Embed texts. Records the last task so tests can check callers pass the right one.
    async def embed(self, texts: Sequence[str], *, task: EmbedTask) -> list[list[float]]:
        # Remember which task the caller asked for.
        self.last_task = task
        # No texts...
        if not texts:
            # ...nothing to do.
            return []
        # Fail if the mode says so.
        _fail(self._mode)
        # Derive numbers from each text's SHA-256 fingerprint (always the same for the same
        #   text).
        # The digest is repeated so any size works (e.g. 1,536 for the real pgvector column).
        return [
            [hashlib.sha256(t.encode()).digest()[i % 32] / 255 for i in range(self._dim)]
            for t in texts
        ]


# A fake reranker: scores documents by how many words they share with the question.
class FakeReranker:
    # Choose the mode.
    def __init__(self, mode: Mode = "ok") -> None:
        # Remember it.
        self._mode = mode

    # Rerank documents.
    async def rerank(self, query: str, documents: Sequence[str], top_n: int) -> list[RerankResult]:
        # Nothing to rank...
        if not documents or top_n <= 0:
            # ...return nothing.
            return []
        # Fail if the mode says so.
        _fail(self._mode)
        # The question's words.
        words = set(query.lower().split())
        # Score each document by shared words.
        scored = [
            RerankResult(index=i, score=float(len(words & set(d.lower().split()))))
            for i, d in enumerate(documents)
        ]
        # Best first, at most top_n.
        return sorted(scored, key=lambda r: r.score, reverse=True)[:top_n]


# A fake AI model that always gives the same reply.
class FakeCompletionClient:
    # Choose the mode and the reply text.
    def __init__(self, mode: Mode = "ok", reply: str = "fake reply") -> None:
        # Remember the mode.
        self._mode = mode
        # Remember the reply.
        self._reply = reply

    # Same inputs as the real clients:
    async def complete(
        # self = this object,
        self,
        # everything after '*' is passed by name,
        *,
        # the system prompt,
        system: str,
        # the conversation,
        messages: Sequence[ChatMessage],
        # the model id,
        model: str,
        # creativity,
        temperature: float,
        # reply length limit.
        max_tokens: int,
    ) -> LLMResponse:
        # Fail if the mode says so.
        _fail(self._mode)
        # Return the fixed reply, counting 1 token each way.
        return LLMResponse(text=self._reply, model=model, tokens_in=1, tokens_out=1)


# A fake speech-to-text.
class FakeSpeechToText:
    """Returns the audio bytes decoded as text, so tests can control the transcript."""

    # Choose the mode.
    def __init__(self, mode: Mode = "ok") -> None:
        # Remember it.
        self._mode = mode

    # Same inputs as the real speech-to-text.
    async def transcribe(
        self, audio: bytes, *, content_type: str, language: str | None = None
    ) -> Transcript:
        # No audio...
        if not audio:
            # ...is refused, like the real adapter.
            raise ValidationError("audio is empty")
        # Fail if the mode says so.
        _fail(self._mode)
        # Pretend the audio bytes ARE the words (handy in tests).
        return Transcript(text=audio.decode(errors="replace"), language=language or "en-IN")


# A fake text-to-speech.
class FakeTextToSpeech:
    # Choose the mode.
    def __init__(self, mode: Mode = "ok") -> None:
        # Remember it.
        self._mode = mode

    # Same inputs as the real text-to-speech.
    async def synthesize(
        self, text: str, *, language: str, voice: str | None = None
    ) -> SynthesizedSpeech:
        # Blank text...
        if not text.strip():
            # ...is refused.
            raise ValidationError("text is empty")
        # Fail if the mode says so.
        _fail(self._mode)
        # Return predictable 'audio': '<language>:<text>' as bytes.
        return SynthesizedSpeech(audio=f"{language}:{text}".encode(), content_type="audio/wav")


# Same safe path pattern as the real Supabase store:
_SEGMENT = r"[A-Za-z0-9_\-][A-Za-z0-9_.\-]{0,199}"
_STORAGE_KEY = re.compile(rf"t/{_SEGMENT}(/{_SEGMENT})+")  # same rule as the real adapter


# A fake file store kept in memory.
class InMemoryObjectStore:
    # Public or private (private by default).
    def __init__(self, *, public: bool = False) -> None:
        # Remember which.
        self._public = public
        # path -> (bytes, type).
        self._objects: dict[str, tuple[bytes, str]] = {}

    # A static method doesn't need `self`.
    @staticmethod
    # Check a path with the same rule as the real store.
    def _check(key: str) -> str:
        # Unsafe path...
        if not _STORAGE_KEY.fullmatch(key):
            # ...refused.
            raise ValidationError("invalid storage key")
        # Safe: return it.
        return key

    # Save a file.
    async def put(self, key: str, data: bytes, content_type: str) -> None:
        # Store bytes and type under the checked path.
        self._objects[self._check(key)] = (data, content_type)

    # Read a file.
    async def get(self, key: str) -> bytes:
        # Try to find it...
        try:
            # ...and return its bytes.
            return self._objects[self._check(key)][0]
        # Not there:
        except KeyError:
            # 404, like the real store.
            raise NotFoundError("object not found") from None

    # Delete a file.
    async def delete(self, key: str) -> None:
        # Remove it if present (missing is fine).
        self._objects.pop(self._check(key), None)

    # Public address.
    def public_url(self, key: str) -> str | None:
        # A fake address for public stores; None for private ones.
        return f"memory://public/{self._check(key)}" if self._public else None

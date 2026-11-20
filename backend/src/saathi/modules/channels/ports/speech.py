# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Contracts for speech: speech-to-text (STT) and text-to-speech (TTS).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Speech ports, split by capability (Interface Segregation).

Used by WhatsApp voice notes (P4.9: speech -> text) and the voice channel (Phase 8.2: both ways).
Language codes are BCP-47 with region, e.g. "bn-IN", "hi-IN", "en-IN".
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
# The text heard, plus the detected language.
class Transcript:
    text: str
    language: str | None  # detected (or requested) language; None if the vendor can't tell


@dataclass(frozen=True, slots=True)
# Generated audio bytes and their format.
class SynthesizedSpeech:
    audio: bytes
    content_type: str  # e.g. "audio/wav"


# Contract: audio -> text.
class SpeechToText(Protocol):
    async def transcribe(
        self, audio: bytes, *, content_type: str, language: str | None = None
    ) -> Transcript:
        """`language=None` asks the vendor to detect it."""
        ...


# Contract: text -> audio.
class TextToSpeech(Protocol):
    async def synthesize(
        self, text: str, *, language: str, voice: str | None = None
    ) -> SynthesizedSpeech:
        """`voice=None` uses the platform's default voice."""
        ...

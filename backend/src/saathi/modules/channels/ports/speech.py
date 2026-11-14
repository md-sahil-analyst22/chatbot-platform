"""Speech ports, split by capability (Interface Segregation).

Used by WhatsApp voice notes (P4.9: speech -> text) and the voice channel (Phase 8.2: both ways).
Language codes are BCP-47 with region, e.g. "bn-IN", "hi-IN", "en-IN".
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str | None  # detected (or requested) language; None if the vendor can't tell


@dataclass(frozen=True, slots=True)
class SynthesizedSpeech:
    audio: bytes
    content_type: str  # e.g. "audio/wav"


class SpeechToText(Protocol):
    async def transcribe(
        self, audio: bytes, *, content_type: str, language: str | None = None
    ) -> Transcript:
        """`language=None` asks the vendor to detect it."""
        ...


class TextToSpeech(Protocol):
    async def synthesize(
        self, text: str, *, language: str, voice: str | None = None
    ) -> SynthesizedSpeech:
        """`voice=None` uses the platform's default voice."""
        ...

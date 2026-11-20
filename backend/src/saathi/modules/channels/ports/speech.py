# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Contracts for speech: speech-to-text (STT) and text-to-speech (TTS).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Speech ports, split by capability (Interface Segregation).

Used by WhatsApp voice notes (P4.9: speech -> text) and the voice channel (Phase 8.2: both ways).
Language codes are BCP-47 with region, e.g. "bn-IN", "hi-IN", "en-IN".
"""

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# The text heard, plus the detected language.
class Transcript:
    # The words heard.
    text: str
    language: str | None  # detected (or requested) language; None if the vendor can't tell


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# Generated audio bytes and their format.
class SynthesizedSpeech:
    # The audio bytes.
    audio: bytes
    content_type: str  # e.g. "audio/wav"


# Contract: audio -> text.
class SpeechToText(Protocol):
    # Audio bytes + their type (+ optional language hint) -> Transcript.
    async def transcribe(
        self, audio: bytes, *, content_type: str, language: str | None = None
    ) -> Transcript:
        """`language=None` asks the vendor to detect it."""
        # `...` = no body: this is only a contract.
        ...


# Contract: text -> audio.
class TextToSpeech(Protocol):
    # Text + language (+ optional voice) -> audio.
    async def synthesize(
        self, text: str, *, language: str, voice: str | None = None
    ) -> SynthesizedSpeech:
        """`voice=None` uses the platform's default voice."""
        # `...` = no body: this is only a contract.
        ...

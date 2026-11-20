# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Speech for Indian languages using Sarvam: 'saaras' turns audio into text, 'bulbul' turns
#       text into audio (ADR-0006).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Sarvam AI speech adapters: speech-to-text (Saaras) and text-to-speech (Bulbul).

Implements SpeechToText and TextToSpeech. Settings: SARVAM_*.
"""

import base64
from typing import Any

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from saathi.modules.channels.adapters import stt_registry, tts_registry
from saathi.modules.channels.ports.speech import SynthesizedSpeech, Transcript
from saathi.platform.errors import (
    ConfigurationError,
    ProviderError,
    ProviderTimeoutError,
    ValidationError,
)

DEFAULT_BASE_URL = "https://api.sarvam.ai"

_EXTENSIONS = {
    "audio/ogg": "ogg",  # WhatsApp voice notes (opus)
    "audio/opus": "opus",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/aac": "aac",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
}


# Languages a TTS model can't speak; those requests use the fallback model instead.
_UNSUPPORTED: dict[str, frozenset[str]] = {"bulbul:v4-flash": frozenset({"ml-IN", "od-IN"})}


# SARVAM_* settings from .env.
class SarvamSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SARVAM_", env_file=".env", extra="ignore")

    api_key: SecretStr | None = None
    base_url: str = DEFAULT_BASE_URL
    stt_model: str = "saaras:v4"
    stt_mode: str = "transcribe"  # same-language text (saaras also offers translate, codemix, ...)
    tts_model: str = "bulbul:v4-flash"
    # Used for languages the main TTS model doesn't support (bulbul:v4-flash: Malayalam, Odia).
    tts_fallback_model: str = "bulbul:v3"
    tts_speaker: str | None = None  # None -> the model's default voice (names differ per model)
    tts_max_chars: int = 1500
    timeout_seconds: float = 20.0


# Audio -> text.
class SarvamSpeechToText:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        model: str = "saaras:v4",
        mode: str = "transcribe",
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 20.0,
    ) -> None:
        self._http = http
        self._model = model
        self._mode = mode
        self._url = f"{base_url.rstrip('/')}/speech-to-text"
        self._headers = {"api-subscription-key": api_key}
        self._timeout = timeout_s

    # Upload audio, get the text and language back.
    async def transcribe(
        self, audio: bytes, *, content_type: str, language: str | None = None
    ) -> Transcript:
        if not audio:
            raise ValidationError("audio is empty")
        base_type = content_type.split(";")[0].strip().lower()
        filename = f"audio.{_EXTENSIONS.get(base_type, 'bin')}"
        try:
            r = await self._http.post(
                self._url,
                headers=self._headers,
                timeout=self._timeout,
                files={"file": (filename, audio, base_type)},
                data={
                    "model": self._model,
                    "mode": self._mode,
                    "language_code": language or "unknown",
                },
            )
            r.raise_for_status()
            body: dict[str, Any] = r.json()
            text = str(body["transcript"])
            detected = body.get("language_code")
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("speech-to-text timed out") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("speech-to-text failed") from exc
        return Transcript(text=text, language=str(detected) if detected else language)


# Text -> audio.
class SarvamTextToSpeech:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        model: str = "bulbul:v4-flash",
        fallback_model: str = "bulbul:v3",
        default_speaker: str | None = None,
        max_chars: int = 1500,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = 20.0,
    ) -> None:
        self._http = http
        self._model = model
        self._fallback_model = fallback_model
        self._default_speaker = default_speaker
        self._max_chars = max_chars
        self._url = f"{base_url.rstrip('/')}/text-to-speech"
        self._headers = {"api-subscription-key": api_key}
        self._timeout = timeout_s

    # Send text, get audio back.
    async def synthesize(
        self, text: str, *, language: str, voice: str | None = None
    ) -> SynthesizedSpeech:
        if not text.strip():
            raise ValidationError("text is empty")
        if len(text) > self._max_chars:
            raise ValidationError(f"text is longer than {self._max_chars} characters")
        model, speaker = self._model, voice or self._default_speaker
        if language in _UNSUPPORTED.get(model, frozenset()):
            # Speaker ids are per model, so the configured voice can't be reused on the fallback.
            model, speaker = self._fallback_model, None
        payload = {"text": text, "target_language_code": language, "model": model}
        if speaker:
            payload["speaker"] = speaker
        try:
            r = await self._http.post(
                self._url, headers=self._headers, timeout=self._timeout, json=payload
            )
            r.raise_for_status()
            body: dict[str, Any] = r.json()
            audio = base64.b64decode(body["audios"][0], validate=True)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("text-to-speech timed out") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
            # binascii.Error (bad base64) is a ValueError subclass
            raise ProviderError("text-to-speech failed") from exc
        if not audio:
            raise ProviderError("text-to-speech returned no audio")
        return SynthesizedSpeech(audio=audio, content_type="audio/wav")


# Read settings; refuse to start without an API key.
def _settings_with_key() -> tuple[SarvamSettings, str]:
    s = SarvamSettings()
    api_key = s.api_key.get_secret_value() if s.api_key else ""
    if not api_key:  # empty counts as missing: fail closed (R16)
        raise ConfigurationError("SARVAM_API_KEY must be set")
    return s, api_key


# Register speech-to-text under the name 'sarvam'.
@stt_registry.register("sarvam")
def create_sarvam_stt(http: httpx.AsyncClient) -> SarvamSpeechToText:
    s, key = _settings_with_key()
    return SarvamSpeechToText(
        http,
        api_key=key,
        model=s.stt_model,
        mode=s.stt_mode,
        base_url=s.base_url,
        timeout_s=s.timeout_seconds,
    )


# Register text-to-speech under the name 'sarvam'.
@tts_registry.register("sarvam")
def create_sarvam_tts(http: httpx.AsyncClient) -> SarvamTextToSpeech:
    s, key = _settings_with_key()
    return SarvamTextToSpeech(
        http,
        api_key=key,
        model=s.tts_model,
        fallback_model=s.tts_fallback_model,
        default_speaker=s.tts_speaker,
        max_chars=s.tts_max_chars,
        base_url=s.base_url,
        timeout_s=s.timeout_seconds,
    )

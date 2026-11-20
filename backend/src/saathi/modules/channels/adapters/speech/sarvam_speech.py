# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Speech for Indian languages using Sarvam: 'saaras' turns audio into text, 'bulbul' turns
#       text into audio (ADR-0006).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Sarvam AI speech adapters: speech-to-text (Saaras) and text-to-speech (Bulbul).

Implements SpeechToText and TextToSpeech. Settings: SARVAM_*.
"""

# base64 — turns bytes into text and back.
import base64

# From typing — type-hint helpers: Any = any type.
from typing import Any

# httpx — the HTTP client we use to call other web services.
import httpx

# From pydantic — checks data against declared types and rules: SecretStr = text that hides
#   itself when printed or logged.
from pydantic import SecretStr

# From pydantic_settings — reads settings from environment variables and .env: BaseSettings =
#   parent class for a group of settings; SettingsConfigDict = where settings are read from (.env,
#   prefix).
from pydantic_settings import BaseSettings, SettingsConfigDict

# From saathi.modules.channels.adapters — speech vendor registries: stt_registry =
#   speech-to-text vendors; tts_registry = text-to-speech vendors.
from saathi.modules.channels.adapters import stt_registry, tts_registry

# From saathi.modules.channels.ports.speech — speech contracts: SynthesizedSpeech = generated
#   audio; Transcript = text heard in audio.
from saathi.modules.channels.ports.speech import SynthesizedSpeech, Transcript

# From saathi.platform.errors — our error types: ConfigurationError = a setting is missing;
#   ProviderError = a vendor failed; ProviderTimeoutError = a vendor was too slow; ValidationError
#   = 422 invalid input.
from saathi.platform.errors import (
    ConfigurationError,
    ProviderError,
    ProviderTimeoutError,
    ValidationError,
)

# Sarvam's API address.
DEFAULT_BASE_URL = "https://api.sarvam.ai"

# Audio type -> file extension to send to Sarvam:
_EXTENSIONS = {
    "audio/ogg": "ogg",  # WhatsApp voice notes (opus)
    # Opus audio,
    "audio/opus": "opus",
    # MP3,
    "audio/mpeg": "mp3",
    # M4A,
    "audio/mp4": "m4a",
    # AAC,
    "audio/aac": "aac",
    # WAV,
    "audio/wav": "wav",
    # WAV (other name),
    "audio/x-wav": "wav",
    # WebM (browser recordings).
    "audio/webm": "webm",
}


# Languages a TTS model can't speak; those requests use the fallback model instead.
_UNSUPPORTED: dict[str, frozenset[str]] = {"bulbul:v4-flash": frozenset({"ml-IN", "od-IN"})}


# SARVAM_* settings from .env.
class SarvamSettings(BaseSettings):
    # Read SARVAM_* variables from .env and ignore the rest.
    model_config = SettingsConfigDict(env_prefix="SARVAM_", env_file=".env", extra="ignore")

    # 🔒 SARVAM_API_KEY (hidden when printed).
    api_key: SecretStr | None = None
    # SARVAM_BASE_URL (normally the default).
    base_url: str = DEFAULT_BASE_URL
    # Speech-to-text model.
    stt_model: str = "saaras:v4"
    stt_mode: str = "transcribe"  # same-language text (saaras also offers translate, codemix, ...)
    # Text-to-speech model.
    tts_model: str = "bulbul:v4-flash"
    # Used for languages the main TTS model doesn't support (bulbul:v4-flash: Malayalam, Odia).
    tts_fallback_model: str = "bulbul:v3"
    tts_speaker: str | None = None  # None -> the model's default voice (names differ per model)
    # Longest text we send for speech in one call.
    tts_max_chars: int = 1500
    # Give up after 20 seconds.
    timeout_seconds: float = 20.0


# Audio -> text.
class SarvamSpeechToText:
    # Built with:
    def __init__(
        self,
        # the shared HTTP client,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        # the model,
        model: str = "saaras:v4",
        # the mode,
        mode: str = "transcribe",
        # the API address,
        base_url: str = DEFAULT_BASE_URL,
        # and the time limit.
        timeout_s: float = 20.0,
    ) -> None:
        # Remember the HTTP client.
        self._http = http
        # Remember the model.
        self._model = model
        # Remember the mode.
        self._mode = mode
        # The speech-to-text address.
        self._url = f"{base_url.rstrip('/')}/speech-to-text"
        # 🔒 The key travels in Sarvam's key header.
        self._headers = {"api-subscription-key": api_key}
        # Remember the time limit.
        self._timeout = timeout_s

    # Upload audio, get the text and language back.
    async def transcribe(
        self, audio: bytes, *, content_type: str, language: str | None = None
    ) -> Transcript:
        # No audio at all...
        if not audio:
            # ...is refused.
            raise ValidationError("audio is empty")
        # The plain type, e.g. 'audio/ogg; codecs=opus' -> 'audio/ogg'.
        base_type = content_type.split(";")[0].strip().lower()
        # A file name with the right extension ('bin' if the type is unknown).
        filename = f"audio.{_EXTENSIONS.get(base_type, 'bin')}"
        # Try the call:
        try:
            # POST to Sarvam
            r = await self._http.post(
                # at the speech-to-text address,
                self._url,
                # with the key header,
                headers=self._headers,
                # within the time limit,
                timeout=self._timeout,
                # uploading the audio as a file,
                files={"file": (filename, audio, base_type)},
                # plus these form fields:
                data={
                    # the model,
                    "model": self._model,
                    # the mode,
                    "mode": self._mode,
                    # the language, or 'unknown' to let Sarvam detect it.
                    "language_code": language or "unknown",
                },
            )
            # An error status counts as a failure.
            r.raise_for_status()
            # Read the JSON answer.
            body: dict[str, Any] = r.json()
            # The text heard.
            text = str(body["transcript"])
            # The language Sarvam detected, if any.
            detected = body.get("language_code")
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("speech-to-text timed out") from exc
        # Network problem or unexpected answer:
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            # vendor error.
            raise ProviderError("speech-to-text failed") from exc
        # Return the text and the detected (or requested) language.
        return Transcript(text=text, language=str(detected) if detected else language)


# Text -> audio.
class SarvamTextToSpeech:
    # Built with:
    def __init__(
        self,
        # the shared HTTP client,
        http: httpx.AsyncClient,
        *,
        api_key: str,
        # the main model,
        model: str = "bulbul:v4-flash",
        # the fallback model,
        fallback_model: str = "bulbul:v3",
        # the default voice (None = the model's own default),
        default_speaker: str | None = None,
        # the longest text allowed,
        max_chars: int = 1500,
        # the API address,
        base_url: str = DEFAULT_BASE_URL,
        # and the time limit.
        timeout_s: float = 20.0,
    ) -> None:
        # Remember the HTTP client.
        self._http = http
        # Remember the main model.
        self._model = model
        # Remember the fallback model.
        self._fallback_model = fallback_model
        # Remember the default voice.
        self._default_speaker = default_speaker
        # Remember the length limit.
        self._max_chars = max_chars
        # The text-to-speech address.
        self._url = f"{base_url.rstrip('/')}/text-to-speech"
        # 🔒 The key travels in Sarvam's key header.
        self._headers = {"api-subscription-key": api_key}
        # Remember the time limit.
        self._timeout = timeout_s

    # Send text, get audio back.
    async def synthesize(
        self, text: str, *, language: str, voice: str | None = None
    ) -> SynthesizedSpeech:
        # Blank text...
        if not text.strip():
            # ...is refused.
            raise ValidationError("text is empty")
        # Too long...
        if len(text) > self._max_chars:
            # ...is refused.
            raise ValidationError(f"text is longer than {self._max_chars} characters")
        # Start with the main model and the requested (or default) voice.
        model, speaker = self._model, voice or self._default_speaker
        # If the main model can't speak this language...
        if language in _UNSUPPORTED.get(model, frozenset()):
            # Speaker ids are per model, so the configured voice can't be reused on the fallback.
            model, speaker = self._fallback_model, None
        # The request body: text, language, model.
        payload = {"text": text, "target_language_code": language, "model": model}
        # If a voice is chosen...
        if speaker:
            # ...add it.
            payload["speaker"] = speaker
        # Try the call:
        try:
            # POST the body as JSON.
            r = await self._http.post(
                self._url, headers=self._headers, timeout=self._timeout, json=payload
            )
            # An error status counts as a failure.
            r.raise_for_status()
            # Read the JSON answer.
            body: dict[str, Any] = r.json()
            # The audio comes back as base64 text; turn it into bytes (strictly).
            audio = base64.b64decode(body["audios"][0], validate=True)
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("text-to-speech timed out") from exc
        # Network problem or unexpected answer:
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
            # binascii.Error (bad base64) is a ValueError subclass
            raise ProviderError("text-to-speech failed") from exc
        # Empty audio...
        if not audio:
            # ...is a vendor error.
            raise ProviderError("text-to-speech returned no audio")
        # Return the audio (WAV).
        return SynthesizedSpeech(audio=audio, content_type="audio/wav")


# Read settings; refuse to start without an API key.
def _settings_with_key() -> tuple[SarvamSettings, str]:
    # Read the SARVAM_* settings.
    s = SarvamSettings()
    # The key as plain text (empty if missing).
    api_key = s.api_key.get_secret_value() if s.api_key else ""
    if not api_key:  # empty counts as missing: fail closed (R16)
        # Refuse to start without it.
        raise ConfigurationError("SARVAM_API_KEY must be set")
    # Return the settings and the key.
    return s, api_key


# Register speech-to-text under the name 'sarvam'.
@stt_registry.register("sarvam")
# The factory the registry calls for speech-to-text.
def create_sarvam_stt(http: httpx.AsyncClient) -> SarvamSpeechToText:
    # Settings + key (refuses without a key).
    s, key = _settings_with_key()
    # Build the speech-to-text client with:
    return SarvamSpeechToText(
        # the HTTP client,
        http,
        # the key,
        api_key=key,
        # the model,
        model=s.stt_model,
        # the mode,
        mode=s.stt_mode,
        # the API address,
        base_url=s.base_url,
        # the time limit.
        timeout_s=s.timeout_seconds,
    )


# Register text-to-speech under the name 'sarvam'.
@tts_registry.register("sarvam")
# The factory the registry calls for text-to-speech.
def create_sarvam_tts(http: httpx.AsyncClient) -> SarvamTextToSpeech:
    # Settings + key (refuses without a key).
    s, key = _settings_with_key()
    # Build the text-to-speech client with:
    return SarvamTextToSpeech(
        # the HTTP client,
        http,
        # the key,
        api_key=key,
        # the main model,
        model=s.tts_model,
        # the fallback model,
        fallback_model=s.tts_fallback_model,
        # the default voice,
        default_speaker=s.tts_speaker,
        # the length limit,
        max_chars=s.tts_max_chars,
        # the API address,
        base_url=s.base_url,
        # the time limit.
        timeout_s=s.timeout_seconds,
    )

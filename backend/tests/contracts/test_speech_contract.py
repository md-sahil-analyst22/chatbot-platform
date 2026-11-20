# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every speech-to-text and text-to-speech adapter must follow.
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# base64 — turns bytes into text and back.
import base64

# json — reads and writes JSON text.
import json

# httpx — the HTTP client we use to call other web services.
import httpx

# pytest — the test framework.
import pytest

# From tests.fakes.providers — fake vendor adapters: FakeSpeechToText = fake speech-to-text;
#   FakeTextToSpeech = fake text-to-speech; Mode = which failure a fake should simulate.
from tests.fakes.providers import FakeSpeechToText, FakeTextToSpeech, Mode

# From saathi.modules.channels.adapters.speech.sarvam_speech — the Sarvam speech adapter:
#   SarvamSpeechToText = Sarvam audio -> text; SarvamTextToSpeech = Sarvam text -> audio.
from saathi.modules.channels.adapters.speech.sarvam_speech import (
    SarvamSpeechToText,
    SarvamTextToSpeech,
)

# From saathi.modules.channels.ports.speech — speech contracts: SpeechToText = speech-to-text
#   contract; TextToSpeech = text-to-speech contract.
from saathi.modules.channels.ports.speech import SpeechToText, TextToSpeech

# From saathi.platform.errors — our error types: ProviderError = a vendor failed;
#   ProviderTimeoutError = a vendor was too slow; ValidationError = 422 invalid input.
from saathi.platform.errors import ProviderError, ProviderTimeoutError, ValidationError

# Test 'audio' (the fake treats these bytes as the words spoken).
AUDIO = b"ar price koto?"


# Helper for fake servers: fail on purpose if the mode says so.
def _failing(mode: Mode, request: httpx.Request) -> httpx.Response | None:
    # timeout mode...
    if mode == "timeout":
        # ...raise a timeout;
        raise httpx.ReadTimeout("timeout", request=request)
    # error mode...
    if mode == "error":
        # ...answer 500;
        return httpx.Response(500, json={"error": "boom"})
    # otherwise no failure.
    return None


# The rules EVERY speech-to-text adapter must follow.
class SpeechToTextContract:
    # Each concrete test class below says which implementation to test; `mode` asks it to
    #   work, fail or time out.
    def make(self, mode: Mode = "ok") -> SpeechToText:
        # The base class itself has no implementation.
        raise NotImplementedError

    # It returns the text and a language.
    async def test_returns_text_and_language(self) -> None:
        # Transcribe with a Bengali hint.
        t = await self.make().transcribe(AUDIO, content_type="audio/ogg", language="bn-IN")
        # Some text.
        assert t.text
        # Some language.
        assert t.language

    # Empty audio is refused.
    async def test_empty_audio_is_rejected(self) -> None:
        # Expect ValidationError from the next line:
        with pytest.raises(ValidationError):
            # transcribe nothing.
            await self.make().transcribe(b"", content_type="audio/ogg")

    # A vendor failure becomes ProviderError.
    async def test_failure_raises_provider_error(self) -> None:
        # Expect ProviderError from the next line:
        with pytest.raises(ProviderError):
            # transcribe in 'error' mode.
            await self.make("error").transcribe(AUDIO, content_type="audio/ogg")

    # A vendor timeout becomes ProviderTimeoutError.
    async def test_timeout_raises_provider_timeout(self) -> None:
        # Expect ProviderTimeoutError from the next line:
        with pytest.raises(ProviderTimeoutError):
            # transcribe in 'timeout' mode.
            await self.make("timeout").transcribe(AUDIO, content_type="audio/ogg")


# The rules EVERY text-to-speech adapter must follow.
class TextToSpeechContract:
    # Each concrete test class below says which implementation to test; `mode` asks it to
    #   work, fail or time out.
    def make(self, mode: Mode = "ok") -> TextToSpeech:
        # The base class itself has no implementation.
        raise NotImplementedError

    # It returns audio with an audio type.
    async def test_returns_audio_with_content_type(self) -> None:
        # Speak a Bengali sentence.
        s = await self.make().synthesize("Dam 500 taka.", language="bn-IN")
        # Some audio.
        assert s.audio
        # An audio/... type.
        assert s.content_type.startswith("audio/")

    # Blank text is refused.
    async def test_empty_text_is_rejected(self) -> None:
        # Expect ValidationError from the next line:
        with pytest.raises(ValidationError):
            # speak only spaces.
            await self.make().synthesize("   ", language="bn-IN")

    # A vendor failure becomes ProviderError.
    async def test_failure_raises_provider_error(self) -> None:
        # Expect ProviderError from the next line:
        with pytest.raises(ProviderError):
            # speak in 'error' mode.
            await self.make("error").synthesize("hi", language="en-IN")

    # A vendor timeout becomes ProviderTimeoutError.
    async def test_timeout_raises_provider_timeout(self) -> None:
        # Expect ProviderTimeoutError from the next line:
        with pytest.raises(ProviderTimeoutError):
            # speak in 'timeout' mode.
            await self.make("timeout").synthesize("hi", language="en-IN")


# Run the speech-to-text rules against the fake.
class TestFakeSpeechToText(SpeechToTextContract):
    # Which implementation:
    def make(self, mode: Mode = "ok") -> SpeechToText:
        # the fake.
        return FakeSpeechToText(mode)


# Run the text-to-speech rules against the fake.
class TestFakeTextToSpeech(TextToSpeechContract):
    # Which implementation:
    def make(self, mode: Mode = "ok") -> TextToSpeech:
        # the fake.
        return FakeTextToSpeech(mode)


# Run the speech-to-text rules against the real Sarvam adapter, with a fake Sarvam server.
class TestSarvamSpeechToText(SpeechToTextContract):
    # The last request the adapter sent.
    request: httpx.Request

    # Which implementation:
    def make(self, mode: Mode = "ok") -> SpeechToText:
        # The fake server answers each request:
        def handler(request: httpx.Request) -> httpx.Response:
            # fail if the mode says so...
            failed = _failing(mode, request)
            # ...(a failure response)...
            if failed:
                # ...is returned;
                return failed
            # otherwise record the request,
            self.request = request
            # and answer with a transcript and a detected language...
            body = {"transcript": "ar dam koto?", "language_code": "bn-IN"}
            # ...as 200.
            return httpx.Response(200, json=body)

        # An HTTP client wired to the fake server.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # The real Sarvam speech-to-text adapter using it.
        return SarvamSpeechToText(http, api_key="k", model="saaras:test")

    # Sarvam-specific: the upload has the right file, model, mode, language and key.
    async def test_sends_multipart_with_model_language_and_key(self) -> None:
        # Transcribe audio whose type has extra parameters.
        await self.make().transcribe(AUDIO, content_type="audio/ogg; codecs=opus")
        # The raw request body.
        body = self.request.read()
        # Sent to /speech-to-text,
        assert self.request.url.path == "/speech-to-text"
        # with the key header,
        assert self.request.headers["api-subscription-key"] == "k"
        # as a file named audio.ogg,
        assert b'filename="audio.ogg"' in body
        # with the model,
        assert b"saaras:test" in body
        # the mode,
        assert b"transcribe" in body
        assert b"unknown" in body  # no language given -> auto-detect
        # and the audio itself.
        assert AUDIO in body


# Run the text-to-speech rules against the real Sarvam adapter, with a fake Sarvam server.
class TestSarvamTextToSpeech(TextToSpeechContract):
    # The last request the adapter sent.
    sent: httpx.Request

    # Which implementation:
    def make(self, mode: Mode = "ok") -> TextToSpeech:
        # The fake server answers each request:
        def handler(request: httpx.Request) -> httpx.Response:
            # fail if the mode says so...
            failed = _failing(mode, request)
            # ...(a failure response)...
            if failed:
                # ...is returned;
                return failed
            # otherwise record the request,
            self.sent = request
            # and answer with base64 'audio'.
            return httpx.Response(200, json={"audios": [base64.b64encode(b"RIFF....").decode()]})

        # An HTTP client wired to the fake server.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # The real adapter with a default voice and a 50-character limit.
        return SarvamTextToSpeech(
            http, api_key="k", default_speaker="simran_hi_conversation", max_chars=50
        )

    # Sarvam-specific: the default voice and the language are sent.
    async def test_uses_default_speaker_and_language(self) -> None:
        # Speak in Hindi.
        await self.make().synthesize("namaskar", language="hi-IN")
        # What was sent.
        sent = json.loads(self.sent.content)
        # The default voice,
        assert sent["speaker"] == "simran_hi_conversation"
        # the language,
        assert sent["target_language_code"] == "hi-IN"
        # the text.
        assert sent["text"] == "namaskar"

    # Sarvam-specific: with no voice configured, none is sent.
    async def test_omits_speaker_when_none_configured(self) -> None:
        # A fake server that...
        def handler(request: httpx.Request) -> httpx.Response:
            # ...records the request...
            self.sent = request
            # ...and answers with audio.
            return httpx.Response(200, json={"audios": [base64.b64encode(b"RIFF").decode()]})

        # An HTTP client wired to it.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # An adapter with no default voice speaks.
        await SarvamTextToSpeech(http, api_key="k").synthesize("hi", language="en-IN")
        # No 'speaker' was sent.
        assert "speaker" not in json.loads(self.sent.content)

    # Sarvam-specific: a language the main model can't speak switches to the fallback model.
    async def test_unsupported_language_uses_fallback_model_without_speaker(self) -> None:
        # Speak Malayalam.
        await self.make().synthesize("namaskaram", language="ml-IN")
        # What was sent.
        sent = json.loads(self.sent.content)
        # The fallback model,
        assert sent["model"] == "bulbul:v3"
        # and no voice (voice names differ per model).
        assert "speaker" not in sent

    # Sarvam-specific: supported languages use the main model.
    async def test_supported_language_uses_main_model(self) -> None:
        # Speak Bengali.
        await self.make().synthesize("nomoskar", language="bn-IN")
        # The main model was used.
        assert json.loads(self.sent.content)["model"] == "bulbul:v4-flash"

    # Text over the limit is refused.
    async def test_text_over_limit_is_rejected(self) -> None:
        # Expect ValidationError from the next line:
        with pytest.raises(ValidationError):
            # 51 characters, limit 50.
            await self.make().synthesize("x" * 51, language="hi-IN")

    # Sarvam-specific: broken audio data becomes ProviderError.
    async def test_bad_audio_payload_raises_provider_error(self) -> None:
        # A fake server...
        def handler(request: httpx.Request) -> httpx.Response:
            # ...that sends invalid base64.
            return httpx.Response(200, json={"audios": ["not base64!!"]})

        # An HTTP client wired to it.
        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        # Expect ProviderError from the next line:
        with pytest.raises(ProviderError):
            # speak.
            await SarvamTextToSpeech(http, api_key="k").synthesize("hi", language="en-IN")

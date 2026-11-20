# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules every speech-to-text and text-to-speech adapter must follow.
# How to run: cd backend && uv run pytest tests/contracts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
import base64
import json

import httpx
import pytest
from tests.fakes.providers import FakeSpeechToText, FakeTextToSpeech, Mode

from saathi.modules.channels.adapters.speech.sarvam_speech import (
    SarvamSpeechToText,
    SarvamTextToSpeech,
)
from saathi.modules.channels.ports.speech import SpeechToText, TextToSpeech
from saathi.platform.errors import ProviderError, ProviderTimeoutError, ValidationError

AUDIO = b"ar price koto?"


def _failing(mode: Mode, request: httpx.Request) -> httpx.Response | None:
    if mode == "timeout":
        raise httpx.ReadTimeout("timeout", request=request)
    if mode == "error":
        return httpx.Response(500, json={"error": "boom"})
    return None


class SpeechToTextContract:
    def make(self, mode: Mode = "ok") -> SpeechToText:
        raise NotImplementedError

    async def test_returns_text_and_language(self) -> None:
        t = await self.make().transcribe(AUDIO, content_type="audio/ogg", language="bn-IN")
        assert t.text
        assert t.language

    async def test_empty_audio_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await self.make().transcribe(b"", content_type="audio/ogg")

    async def test_failure_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError):
            await self.make("error").transcribe(AUDIO, content_type="audio/ogg")

    async def test_timeout_raises_provider_timeout(self) -> None:
        with pytest.raises(ProviderTimeoutError):
            await self.make("timeout").transcribe(AUDIO, content_type="audio/ogg")


class TextToSpeechContract:
    def make(self, mode: Mode = "ok") -> TextToSpeech:
        raise NotImplementedError

    async def test_returns_audio_with_content_type(self) -> None:
        s = await self.make().synthesize("Dam 500 taka.", language="bn-IN")
        assert s.audio
        assert s.content_type.startswith("audio/")

    async def test_empty_text_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await self.make().synthesize("   ", language="bn-IN")

    async def test_failure_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError):
            await self.make("error").synthesize("hi", language="en-IN")

    async def test_timeout_raises_provider_timeout(self) -> None:
        with pytest.raises(ProviderTimeoutError):
            await self.make("timeout").synthesize("hi", language="en-IN")


class TestFakeSpeechToText(SpeechToTextContract):
    def make(self, mode: Mode = "ok") -> SpeechToText:
        return FakeSpeechToText(mode)


class TestFakeTextToSpeech(TextToSpeechContract):
    def make(self, mode: Mode = "ok") -> TextToSpeech:
        return FakeTextToSpeech(mode)


class TestSarvamSpeechToText(SpeechToTextContract):
    request: httpx.Request

    def make(self, mode: Mode = "ok") -> SpeechToText:
        def handler(request: httpx.Request) -> httpx.Response:
            failed = _failing(mode, request)
            if failed:
                return failed
            self.request = request
            body = {"transcript": "ar dam koto?", "language_code": "bn-IN"}
            return httpx.Response(200, json=body)

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return SarvamSpeechToText(http, api_key="k", model="saaras:test")

    async def test_sends_multipart_with_model_language_and_key(self) -> None:
        await self.make().transcribe(AUDIO, content_type="audio/ogg; codecs=opus")
        body = self.request.read()
        assert self.request.url.path == "/speech-to-text"
        assert self.request.headers["api-subscription-key"] == "k"
        assert b'filename="audio.ogg"' in body
        assert b"saaras:test" in body
        assert b"transcribe" in body
        assert b"unknown" in body  # no language given -> auto-detect
        assert AUDIO in body


class TestSarvamTextToSpeech(TextToSpeechContract):
    sent: httpx.Request

    def make(self, mode: Mode = "ok") -> TextToSpeech:
        def handler(request: httpx.Request) -> httpx.Response:
            failed = _failing(mode, request)
            if failed:
                return failed
            self.sent = request
            return httpx.Response(200, json={"audios": [base64.b64encode(b"RIFF....").decode()]})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return SarvamTextToSpeech(
            http, api_key="k", default_speaker="simran_hi_conversation", max_chars=50
        )

    async def test_uses_default_speaker_and_language(self) -> None:
        await self.make().synthesize("namaskar", language="hi-IN")
        sent = json.loads(self.sent.content)
        assert sent["speaker"] == "simran_hi_conversation"
        assert sent["target_language_code"] == "hi-IN"
        assert sent["text"] == "namaskar"

    async def test_omits_speaker_when_none_configured(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.sent = request
            return httpx.Response(200, json={"audios": [base64.b64encode(b"RIFF").decode()]})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await SarvamTextToSpeech(http, api_key="k").synthesize("hi", language="en-IN")
        assert "speaker" not in json.loads(self.sent.content)

    async def test_unsupported_language_uses_fallback_model_without_speaker(self) -> None:
        await self.make().synthesize("namaskaram", language="ml-IN")
        sent = json.loads(self.sent.content)
        assert sent["model"] == "bulbul:v3"
        assert "speaker" not in sent

    async def test_supported_language_uses_main_model(self) -> None:
        await self.make().synthesize("nomoskar", language="bn-IN")
        assert json.loads(self.sent.content)["model"] == "bulbul:v4-flash"

    async def test_text_over_limit_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            await self.make().synthesize("x" * 51, language="hi-IN")

    async def test_bad_audio_payload_raises_provider_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"audios": ["not base64!!"]})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(ProviderError):
            await SarvamTextToSpeech(http, api_key="k").synthesize("hi", language="en-IN")

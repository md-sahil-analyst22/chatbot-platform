"""Provider registries for this module. Adapters register themselves when imported
(bootstrap/providers.py imports them explicitly)."""

from saathi.modules.channels.ports.speech import SpeechToText, TextToSpeech
from saathi.platform.providers import ProviderRegistry

stt_registry: ProviderRegistry[SpeechToText] = ProviderRegistry("speech-to-text")
tts_registry: ProviderRegistry[TextToSpeech] = ProviderRegistry("text-to-speech")

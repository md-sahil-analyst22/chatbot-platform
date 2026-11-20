# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The registries ('phone books') for speech-to-text and text-to-speech vendors.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Provider registries for this module. Adapters register themselves when imported
(bootstrap/providers.py imports them explicitly)."""

# From saathi.modules.channels.ports.speech — speech contracts: SpeechToText = speech-to-text
#   contract; TextToSpeech = text-to-speech contract.
from saathi.modules.channels.ports.speech import SpeechToText, TextToSpeech

# From saathi.platform.providers — the vendor registry: ProviderRegistry = the 'phone book' of
#   vendor adapters.
from saathi.platform.providers import ProviderRegistry

# Phone book of speech-to-text vendors.
stt_registry: ProviderRegistry[SpeechToText] = ProviderRegistry("speech-to-text")
# Phone book of text-to-speech vendors.
tts_registry: ProviderRegistry[TextToSpeech] = ProviderRegistry("text-to-speech")

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The registry ('phone book') of AI language model adapters.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Provider registries for this module. Adapters register themselves when imported
(bootstrap/providers.py imports them explicitly)."""

# From saathi.modules.conversation.ports.llm — AI language-model contracts: CompletionClient =
#   contract: messages in, reply out.
from saathi.modules.conversation.ports.llm import CompletionClient

# From saathi.platform.providers — the vendor registry: ProviderRegistry = the 'phone book' of
#   vendor adapters.
from saathi.platform.providers import ProviderRegistry

completion_registry: ProviderRegistry[CompletionClient] = ProviderRegistry("llm-completion")
# P3.8: streaming_registry: ProviderRegistry[StreamingClient] = ProviderRegistry("llm-streaming")

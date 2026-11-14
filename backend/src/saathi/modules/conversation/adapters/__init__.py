"""Provider registries for this module. Adapters register themselves when imported
(bootstrap/providers.py imports them explicitly)."""

from saathi.modules.conversation.ports.llm import CompletionClient
from saathi.platform.providers import ProviderRegistry

completion_registry: ProviderRegistry[CompletionClient] = ProviderRegistry("llm-completion")
# P3.8: streaming_registry: ProviderRegistry[StreamingClient] = ProviderRegistry("llm-streaming")

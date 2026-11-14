"""Provider registries for this module. Adapters register themselves when imported
(bootstrap/providers.py imports them explicitly)."""

from saathi.modules.knowledge.ports.providers import DocumentParser, Embedder, Reranker
from saathi.platform.providers import ProviderRegistry

parser_registry: ProviderRegistry[DocumentParser] = ProviderRegistry("parser")
embedder_registry: ProviderRegistry[Embedder] = ProviderRegistry("embedder")
reranker_registry: ProviderRegistry[Reranker] = ProviderRegistry("reranker")

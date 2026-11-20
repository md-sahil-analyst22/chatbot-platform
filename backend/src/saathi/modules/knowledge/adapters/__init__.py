# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The registries ('phone books') for parsers, embedders and rerankers.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Provider registries for this module. Adapters register themselves when imported
(bootstrap/providers.py imports them explicitly)."""

# From saathi.modules.knowledge.ports.providers — parser, embedder and reranker contracts:
#   DocumentParser = contract: file -> text; Embedder = contract: text -> vectors; Reranker =
#   contract: best documents first.
from saathi.modules.knowledge.ports.providers import DocumentParser, Embedder, Reranker

# From saathi.platform.providers — the vendor registry: ProviderRegistry = the 'phone book' of
#   vendor adapters.
from saathi.platform.providers import ProviderRegistry

# Phone book of document parsers.
parser_registry: ProviderRegistry[DocumentParser] = ProviderRegistry("parser")
# Phone book of embedders.
embedder_registry: ProviderRegistry[Embedder] = ProviderRegistry("embedder")
# Phone book of rerankers.
reranker_registry: ProviderRegistry[Reranker] = ProviderRegistry("reranker")

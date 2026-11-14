from saathi.platform.providers import ProviderRegistry
from saathi.platform.storage.object_store import ObjectStore

# Adapters (supabase_store.py, ...) register here; bootstrap/providers.py imports them.
object_store_registry: ProviderRegistry[ObjectStore] = ProviderRegistry("object-store")

__all__ = ["ObjectStore", "object_store_registry"]

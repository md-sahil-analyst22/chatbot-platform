# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Exposes the ObjectStore contract and the storage registry (the phone book of storage
#       vendors).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From saathi.platform.providers — the vendor registry: ProviderRegistry = the 'phone book' of
#   vendor adapters.
from saathi.platform.providers import ProviderRegistry

# From saathi.platform.storage.object_store — the file storage contract: ObjectStore = the file
#   storage contract.
from saathi.platform.storage.object_store import ObjectStore

# Adapters (supabase_store.py, ...) register here; bootstrap/providers.py imports them.
object_store_registry: ProviderRegistry[ObjectStore] = ProviderRegistry("object-store")

__all__ = ["ObjectStore", "object_store_registry"]

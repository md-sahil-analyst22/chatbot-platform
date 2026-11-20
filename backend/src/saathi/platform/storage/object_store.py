# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contract for file storage: put, get, delete, public_url.
# Why: Code needing files depends on this contract, not on Supabase directly (rule R7).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Object storage port, shared by document uploads (knowledge) and logos (tenancy).

Keys are always tenant-prefixed: "t/{tenant_id}/..." so a bucket policy or a bug can never mix
two tenants' files. Adapters (Supabase Storage / S3 / R2) arrive with the first upload task.
"""

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol


# Any storage vendor must provide these four operations.
class ObjectStore(Protocol):
    # Save bytes under a key (file path).
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    # Read the bytes stored under a key.
    async def get(self, key: str) -> bytes: ...

    # Delete the file at a key.
    async def delete(self, key: str) -> None: ...

    # The public web address of a file, or None if the store is private.
    def public_url(self, key: str) -> str | None:
        """URL for public assets (logos); None for private objects (documents)."""
        # `...` = no body: this is only a contract.
        ...

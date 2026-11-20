# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contract for file storage: put, get, delete, public_url.
# Why: Code needing files depends on this contract, not on Supabase directly (rule R7).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Object storage port, shared by document uploads (knowledge) and logos (tenancy).

Keys are always tenant-prefixed: "t/{tenant_id}/..." so a bucket policy or a bug can never mix
two tenants' files. Adapters (Supabase Storage / S3 / R2) arrive with the first upload task.
"""

from typing import Protocol


# Any storage vendor must provide these four operations.
class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    def public_url(self, key: str) -> str | None:
        """URL for public assets (logos); None for private objects (documents)."""
        ...

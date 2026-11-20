# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Contract: 'give me the API key to use for this tenant and vendor'.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol


# Platform key today; tenants' own keys from Phase 8.
class CredentialSource(Protocol):
    """Where the API key for a provider comes from, for a given tenant.

    Today: the platform's own keys. Phase 8 (Pro): the tenant's own key from the credentials
    vault first, then the platform key if the plan allows a fallback.
    """

    # The key for this tenant + vendor, or None.
    async def api_key_for(self, tenant_id: str, provider: str) -> str | None: ...

from typing import Protocol


class CredentialSource(Protocol):
    """Where the API key for a provider comes from, for a given tenant.

    Today: the platform's own keys. Phase 8 (Pro): the tenant's own key from the credentials
    vault first, then the platform key if the plan allows a fallback.
    """

    async def api_key_for(self, tenant_id: str, provider: str) -> str | None: ...

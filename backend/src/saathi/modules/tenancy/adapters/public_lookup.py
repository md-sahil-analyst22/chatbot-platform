"""Public key -> tenant lookup for the widget, run BEFORE a tenant context exists.

Under RLS the app role cannot read `bots` without a tenant, so the lookup goes through a narrow
SECURITY DEFINER function created in the Phase 1 migration (P1.11):

    CREATE FUNCTION resolve_bot_public_key(p_key text)
    RETURNS TABLE (tenant_id uuid, bot_id uuid)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
        SELECT b.tenant_id, b.id FROM bots b WHERE b.public_key = p_key
    $$;
    REVOKE ALL ON FUNCTION resolve_bot_public_key(text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION resolve_bot_public_key(text) TO saathi_app;

It returns two ids and nothing else, so it cannot be used to read tenant data.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from saathi.modules.tenancy.ports.repositories import PublicBotRef


class SqlAlchemyPublicBotLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(self, public_key: str) -> PublicBotRef | None:
        result = await self._session.execute(
            text("SELECT tenant_id, bot_id FROM resolve_bot_public_key(:k)"), {"k": public_key}
        )
        row = result.first()
        return PublicBotRef(tenant_id=row.tenant_id, bot_id=row.bot_id) if row else None

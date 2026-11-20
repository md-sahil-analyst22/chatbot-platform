# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Finds which tenant and bot a public widget key belongs to.
# Why special: Row-level security hides all bots until we know the tenant, so this uses a narrow
#              database function that returns only two ids.
# ─────────────────────────────────────────────────────────────────────────────────────────────
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

# From sqlalchemy — SQLAlchemy, our database toolkit: text = a raw SQL snippet.
from sqlalchemy import text

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncSession =
#   one unit of database work.
from sqlalchemy.ext.asyncio import AsyncSession

# From saathi.modules.tenancy.ports.repositories — tenancy storage contracts: PublicBotRef =
#   tenant + bot for a widget key.
from saathi.modules.tenancy.ports.repositories import PublicBotRef


# Calls the database function resolve_bot_public_key().
class SqlAlchemyPublicBotLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # Key -> (tenant, bot), or None if the key is unknown.
    async def resolve(self, public_key: str) -> PublicBotRef | None:
        result = await self._session.execute(
            text("SELECT tenant_id, bot_id FROM resolve_bot_public_key(:k)"), {"k": public_key}
        )
        row = result.first()
        return PublicBotRef(tenant_id=row.tenant_id, bot_id=row.bot_id) if row else None

"""Tenant context for Postgres Row-Level Security.

Every tenant-owned table has a policy like this (migration 0002):

    ALTER TABLE bots ENABLE ROW LEVEL SECURITY;
    ALTER TABLE bots FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON bots
        USING      (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

If app.tenant_id is not set, current_setting(..., true) returns NULL (or '' on a pooled
connection that used it earlier); nullif() makes both NULL, so the policy matches no rows ->
fail closed.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def set_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    """Bind the tenant for the CURRENT transaction only.

    set_config(..., is_local => true) behaves like SET LOCAL: it resets at COMMIT/ROLLBACK,
    so a pooled connection can never carry one tenant's context into another request.
    """
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )


@asynccontextmanager
async def tenant_session(
    sessionmaker: async_sessionmaker[AsyncSession], tenant_id: UUID
) -> AsyncIterator[AsyncSession]:
    """Session + transaction with the tenant bound. Commits on success, rolls back on error."""
    async with sessionmaker() as session, session.begin():
        await set_tenant(session, tenant_id)
        yield session

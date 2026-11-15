"""Verified user -> tenant memberships, run BEFORE a tenant context exists (ADR-0007).

user_accounts is under RLS, so the app role reads it through the narrow SECURITY DEFINER
function resolve_user_membership() (migration 0003), which returns only tenant ids and roles.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saathi.platform.security.auth import Membership, Role

# More rows than this means something is wrong; never load an unbounded list per request.
_MAX_MEMBERSHIPS = 20


class SqlAlchemyMembershipLookup:
    """Implements MembershipLookup with its own short session (no tenant bound)."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def memberships(self, auth_user_id: str) -> list[Membership]:
        async with self._sessionmaker() as session:
            rows = await session.execute(
                text("SELECT tenant_id, role FROM resolve_user_membership(:uid) LIMIT :max"),
                {"uid": auth_user_id, "max": _MAX_MEMBERSHIPS},
            )
            return [Membership(tenant_id=r.tenant_id, role=Role(r.role)) for r in rows]

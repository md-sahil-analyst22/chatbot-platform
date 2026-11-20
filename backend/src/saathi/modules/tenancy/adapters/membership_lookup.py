# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 After a login is verified, finds which workspace(s) the user belongs to and with what
#       role.
# Why special: Runs before a tenant is known, through the narrow database function
#              resolve_user_membership().
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Verified user -> tenant memberships, run BEFORE a tenant context exists (ADR-0007).

user_accounts is under RLS, so the app role reads it through the narrow SECURITY DEFINER
function resolve_user_membership() (migration 0003), which returns only tenant ids and roles.
"""

# From sqlalchemy — SQLAlchemy, our database toolkit: text = a raw SQL snippet.
from sqlalchemy import text

# From sqlalchemy.ext.asyncio — SQLAlchemy's async (non-blocking) database tools: AsyncSession =
#   one unit of database work; async_sessionmaker = factory that creates sessions.
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# From saathi.platform.security.auth — who is calling and what they may do: Membership = one
#   (workspace, role) pair; Role = viewer/agent/admin/owner.
from saathi.platform.security.auth import Membership, Role

# More rows than this means something is wrong; never load an unbounded list per request.
_MAX_MEMBERSHIPS = 20


# Used by the login checker (platform/security/jwt_verifier.py).
class SqlAlchemyMembershipLookup:
    """Implements MembershipLookup with its own short session (no tenant bound)."""

    # Gets the session factory (it opens its own short session per lookup).
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        # Remember it.
        self._sessionmaker = sessionmaker

    # User id -> list of (tenant, role).
    async def memberships(self, auth_user_id: str) -> list[Membership]:
        # Open a short session (no tenant context yet).
        async with self._sessionmaker() as session:
            # Run:
            rows = await session.execute(
                # 🔒 the narrow lookup function, at most _MAX_MEMBERSHIPS rows,
                text("SELECT tenant_id, role FROM resolve_user_membership(:uid) LIMIT :max"),
                # with the user id and the limit passed as parameters (never pasted into the
                #   SQL).
                {"uid": auth_user_id, "max": _MAX_MEMBERSHIPS},
            )
            # Turn each row into a Membership (role text -> Role).
            return [Membership(tenant_id=r.tenant_id, role=Role(r.role)) for r in rows]

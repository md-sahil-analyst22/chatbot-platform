# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Who is calling (Principal), what they may do (Role), and the contracts for checking
#       logins.
# Used by: Every service method starts with require_role(principal, ...).
# Roles: viewer < agent < admin < owner. Each role can do everything the lower ones can.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Authenticated principal + role checks. The JWT verifier adapter is plugged in at P1.7."""

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.platform.errors — our error types: AuthorizationError = 403 role not allowed.
from saathi.platform.errors import AuthorizationError


# The four roles a user can have in a workspace.
class Role(StrEnum):
    VIEWER = "viewer"
    AGENT = "agent"
    ADMIN = "admin"
    OWNER = "owner"


# Turns roles into numbers so they can be compared.
_RANK = {Role.VIEWER: 0, Role.AGENT: 1, Role.ADMIN: 2, Role.OWNER: 3}


@dataclass(frozen=True, slots=True)
# The verified caller: user id, tenant id and role. The tenant ALWAYS comes from here, never
# from the request body (R8).
class Principal:
    """Who is calling. tenant_id comes from the verified token - never from the request body."""

    user_id: str
    tenant_id: UUID
    role: Role


# Contract: turn a login token into a Principal, or refuse.
class TokenVerifier(Protocol):
    async def verify(self, token: str) -> Principal:
        """Return the principal or raise AuthenticationError. Must fail closed."""
        ...


@dataclass(frozen=True, slots=True)
# One (workspace, role) pair a user belongs to.
class Membership:
    tenant_id: UUID
    role: Role


# Contract: find a verified user's memberships (implemented in tenancy/adapters).
class MembershipLookup(Protocol):
    """Which tenants a verified user belongs to (ADR-0007). Runs before any tenant context."""

    async def memberships(self, auth_user_id: str) -> list[Membership]: ...


# Stop with 403 if the caller's role is lower than required.
def require_role(principal: Principal, minimum: Role) -> None:
    if _RANK[principal.role] < _RANK[minimum]:
        raise AuthorizationError(f"requires role >= {minimum.value}")

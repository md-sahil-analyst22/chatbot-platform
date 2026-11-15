"""Authenticated principal + role checks. The JWT verifier adapter is plugged in at P1.7."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from saathi.platform.errors import AuthorizationError


class Role(StrEnum):
    VIEWER = "viewer"
    AGENT = "agent"
    ADMIN = "admin"
    OWNER = "owner"


_RANK = {Role.VIEWER: 0, Role.AGENT: 1, Role.ADMIN: 2, Role.OWNER: 3}


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is calling. tenant_id comes from the verified token - never from the request body."""

    user_id: str
    tenant_id: UUID
    role: Role


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> Principal:
        """Return the principal or raise AuthenticationError. Must fail closed."""
        ...


@dataclass(frozen=True, slots=True)
class Membership:
    tenant_id: UUID
    role: Role


class MembershipLookup(Protocol):
    """Which tenants a verified user belongs to (ADR-0007). Runs before any tenant context."""

    async def memberships(self, auth_user_id: str) -> list[Membership]: ...


def require_role(principal: Principal, minimum: Role) -> None:
    if _RANK[principal.role] < _RANK[minimum]:
        raise AuthorizationError(f"requires role >= {minimum.value}")

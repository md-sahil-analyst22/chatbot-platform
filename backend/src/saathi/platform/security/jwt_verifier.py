"""Supabase access-token verifier (implements TokenVerifier, ADR-0007).

1. Verify the JWT locally against the cached JWKS: allowed algorithms, issuer, audience, expiry.
2. Resolve the verified user to exactly one (tenant, role) through MembershipLookup.

Every failure raises AuthenticationError / AuthorizationError with a generic message; the
precise reason is logged without the token (R16, R17).
"""

import time
from collections.abc import Callable
from typing import Any, NoReturn

import httpx
import jwt
import structlog

from saathi.platform.errors import AuthenticationError, AuthorizationError, InfrastructureError
from saathi.platform.security.auth import MembershipLookup, Principal

# Asymmetric only: HS256 would let the PUBLIC key be used as an HMAC secret; "none" is no
# signature at all.
ALLOWED_ALGORITHMS = ("ES256", "RS256")
JWKS_TTL_SECONDS = 600.0
# A token with an unknown key id may trigger a JWKS refresh at most this often.
UNKNOWN_KID_REFRESH_SECONDS = 60.0
LEEWAY_SECONDS = 30
JWKS_TIMEOUT_SECONDS = 5.0

_INVALID = "invalid or expired token"


class JwksTokenVerifier:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        memberships: MembershipLookup,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._http = http
        self._jwks_url = jwks_url
        self._issuer = issuer
        self._audience = audience
        self._memberships = memberships
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None

    async def verify(self, token: str) -> Principal:
        claims = await self._verified_claims(token)
        user_id = str(claims["sub"])
        found = await self._memberships.memberships(user_id)
        if not found:
            structlog.get_logger().info("auth.no_membership")
            raise AuthorizationError("your account has no access to any workspace")
        if len(found) > 1:
            # Tenant switching isn't designed yet; never guess which tenant the user meant.
            structlog.get_logger().info("auth.multiple_memberships", count=len(found))
            raise AuthorizationError("your account belongs to more than one workspace")
        return Principal(user_id=user_id, tenant_id=found[0].tenant_id, role=found[0].role)

    async def _verified_claims(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            self._reject("malformed")
        alg, kid = header.get("alg"), header.get("kid")
        if alg not in ALLOWED_ALGORITHMS or not isinstance(kid, str):
            self._reject("disallowed_alg_or_missing_kid")
        key = await self._key_for(kid)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=list(ALLOWED_ALGORITHMS),
                audience=self._audience,
                issuer=self._issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            self._reject(type(exc).__name__)
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            self._reject("missing_sub")
        return claims

    async def _key_for(self, kid: str) -> jwt.PyJWK:
        now = self._clock()
        stale = self._fetched_at is None or now - self._fetched_at > JWKS_TTL_SECONDS
        may_refresh_for_kid = (
            self._fetched_at is None or now - self._fetched_at > UNKNOWN_KID_REFRESH_SECONDS
        )
        if stale or (kid not in self._keys and may_refresh_for_kid):
            await self._refresh(keep_old_on_error=bool(self._keys))
        key = self._keys.get(kid)
        if key is None:
            self._reject("unknown_kid")
        return key

    async def _refresh(self, *, keep_old_on_error: bool) -> None:
        try:
            r = await self._http.get(self._jwks_url, timeout=JWKS_TIMEOUT_SECONDS)
            r.raise_for_status()
            keyset = jwt.PyJWKSet.from_dict(r.json())
        except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
            structlog.get_logger().warning("auth.jwks_fetch_failed", error=type(exc).__name__)
            if keep_old_on_error:  # keep serving with the last good keys during a blip
                self._fetched_at = self._clock()
                return
            # No keys at all: we can't verify anything, so nothing gets in (fail closed).
            raise InfrastructureError("authentication is temporarily unavailable") from exc
        self._keys = {k.key_id: k for k in keyset.keys if k.key_id}
        self._fetched_at = self._clock()

    @staticmethod
    def _reject(reason: str) -> NoReturn:
        structlog.get_logger().info("auth.token_rejected", reason=reason)
        raise AuthenticationError(_INVALID)

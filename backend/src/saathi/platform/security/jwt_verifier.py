# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Checks Supabase login tokens and finds the caller's workspace (ADR-0007).
# Steps: 1) check the token's signature with Supabase's public keys, 2) check issuer, audience
#        and expiry, 3) look up exactly one workspace for the user.
# Security: Only ES256/RS256 are accepted. Every failure gives the same vague message to the
#           caller, while the precise reason is logged (never the token).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Supabase access-token verifier (implements TokenVerifier, ADR-0007).

1. Verify the JWT locally against the cached JWKS: allowed algorithms, issuer, audience, expiry.
2. Resolve the verified user to exactly one (tenant, role) through MembershipLookup.

Every failure raises AuthenticationError / AuthorizationError with a generic message; the
precise reason is logged without the token (R16, R17).
"""

# time — clocks and timers.
import time

# From collections.abc — standard type names for collections: Callable = type for a function.
from collections.abc import Callable

# From typing — type-hint helpers: Any = any type; NoReturn = a function that always raises.
from typing import Any, NoReturn

# httpx — the HTTP client we use to call other web services.
import httpx

# jwt — PyJWT, reads and checks login tokens (JWTs).
import jwt

# structlog — structured logging (JSON log lines).
import structlog

# From saathi.platform.errors — our error types: AuthenticationError = 401 not logged in;
#   AuthorizationError = 403 role not allowed; InfrastructureError = our side broke.
from saathi.platform.errors import AuthenticationError, AuthorizationError, InfrastructureError

# From saathi.platform.security.auth — who is calling and what they may do: MembershipLookup =
#   contract: find a user's workspaces; Principal = the verified caller.
from saathi.platform.security.auth import MembershipLookup, Principal

# Asymmetric only: HS256 would let the PUBLIC key be used as an HMAC secret; "none" is no
# signature at all.
# Only asymmetric signatures. HS256 would let an attacker sign tokens with our PUBLIC key.
ALLOWED_ALGORITHMS = ("ES256", "RS256")
# Public keys are cached for 10 minutes, so we don't call Supabase on every request.
JWKS_TTL_SECONDS = 600.0
# A token with an unknown key id may trigger a JWKS refresh at most this often.
# Unknown key ids trigger at most one refresh per minute (stops attackers hammering Supabase).
UNKNOWN_KID_REFRESH_SECONDS = 60.0
LEEWAY_SECONDS = 30
JWKS_TIMEOUT_SECONDS = 5.0

_INVALID = "invalid or expired token"


# The real login checker. Built once by the container.
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

    # Main entry: token in, Principal out (or an error).
    async def verify(self, token: str) -> Principal:
        claims = await self._verified_claims(token)
        user_id = str(claims["sub"])
        found = await self._memberships.memberships(user_id)
        # Valid login, but no workspace yet -> 403.
        if not found:
            structlog.get_logger().info("auth.no_membership")
            raise AuthorizationError("your account has no access to any workspace")
        # In two workspaces: we never guess which one -> 403 until tenant switching exists.
        if len(found) > 1:
            # Tenant switching isn't designed yet; never guess which tenant the user meant.
            structlog.get_logger().info("auth.multiple_memberships", count=len(found))
            raise AuthorizationError("your account belongs to more than one workspace")
        return Principal(user_id=user_id, tenant_id=found[0].tenant_id, role=found[0].role)

    # Checks the token itself and returns its contents ('claims').
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

    # Find the public key that signed this token (refreshing the cached keys when needed).
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

    # Download Supabase's public keys. If that fails, keep using the old ones; with none at all,
    # refuse everything.
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
    # Log why (without the token) and answer 401 'invalid or expired token'.
    def _reject(reason: str) -> NoReturn:
        structlog.get_logger().info("auth.token_rejected", reason=reason)
        raise AuthenticationError(_INVALID)

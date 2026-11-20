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
# Allow 30 seconds of clock difference between Supabase and us.
LEEWAY_SECONDS = 30
# Give up downloading the public keys after 5 seconds.
JWKS_TIMEOUT_SECONDS = 5.0

# The one vague message callers see for every token problem.
_INVALID = "invalid or expired token"


# The real login checker. Built once by the container.
class JwksTokenVerifier:
    # Created once by the container with:
    def __init__(
        # self = this object itself (Python passes it in automatically).
        self,
        # the shared HTTP client,
        http: httpx.AsyncClient,
        # Everything after '*' must be passed by name, e.g. api_key=...
        *,
        # where Supabase publishes its public keys,
        jwks_url: str,
        # who must have issued the token,
        issuer: str,
        # who the token must be meant for,
        audience: str,
        # how to find the user's workspace,
        memberships: MembershipLookup,
        # and a clock (tests replace it to fake the passing of time).
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # Remember the HTTP client.
        self._http = http
        # Remember where the keys are published.
        self._jwks_url = jwks_url
        # Remember the expected issuer.
        self._issuer = issuer
        # Remember the expected audience.
        self._audience = audience
        # Remember the membership lookup.
        self._memberships = memberships
        # Remember the clock.
        self._clock = clock
        # Cached public keys: key id -> key (empty at start).
        self._keys: dict[str, jwt.PyJWK] = {}
        # When the keys were last downloaded (None = never).
        self._fetched_at: float | None = None

    # Main entry: token in, Principal out (or an error).
    async def verify(self, token: str) -> Principal:
        # Check the token and get its contents.
        claims = await self._verified_claims(token)
        # The user id inside the token.
        user_id = str(claims["sub"])
        # Look up which workspace(s) this user belongs to.
        found = await self._memberships.memberships(user_id)
        # Valid login, but no workspace yet -> 403.
        if not found:
            # Log it (no personal data)...
            structlog.get_logger().info("auth.no_membership")
            # ...and answer 403.
            raise AuthorizationError("your account has no access to any workspace")
        # In two workspaces: we never guess which one -> 403 until tenant switching exists.
        if len(found) > 1:
            # Tenant switching isn't designed yet; never guess which tenant the user meant.
            structlog.get_logger().info("auth.multiple_memberships", count=len(found))
            # Answer 403.
            raise AuthorizationError("your account belongs to more than one workspace")
        # Exactly one workspace: build the verified caller.
        return Principal(user_id=user_id, tenant_id=found[0].tenant_id, role=found[0].role)

    # Checks the token itself and returns its contents ('claims').
    async def _verified_claims(self, token: str) -> dict[str, Any]:
        # Try to read the token's header (not yet trusted!)...
        try:
            # ...which says which algorithm and which key signed it.
            header = jwt.get_unverified_header(token)
        # Not even a readable token:
        except jwt.PyJWTError:
            # reject it.
            self._reject("malformed")
        # The algorithm and the key id from the header.
        alg, kid = header.get("alg"), header.get("kid")
        # 🔒 A forbidden algorithm, or no key id...
        if alg not in ALLOWED_ALGORITHMS or not isinstance(kid, str):
            # ...means reject.
            self._reject("disallowed_alg_or_missing_kid")
        # Get the public key with that id (downloading if needed).
        key = await self._key_for(kid)
        # Now check the token for real:
        try:
            # decode it, verifying...
            claims: dict[str, Any] = jwt.decode(
                # the token,
                token,
                # against that public key,
                key,
                # only with our allowed algorithms,
                algorithms=list(ALLOWED_ALGORITHMS),
                # for the right audience,
                audience=self._audience,
                # from the right issuer,
                issuer=self._issuer,
                # allowing a little clock difference,
                leeway=LEEWAY_SECONDS,
                # and these fields must be present: expiry, issued-at, user, issuer, audience.
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        # Any check failed (expired, bad signature, wrong issuer...):
        except jwt.PyJWTError as exc:
            # reject, logging only the kind of failure.
            self._reject(type(exc).__name__)
        # The user id must be non-empty text...
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            # ...otherwise reject.
            self._reject("missing_sub")
        # All good: return the token's contents.
        return claims

    # Find the public key that signed this token (refreshing the cached keys when needed).
    async def _key_for(self, kid: str) -> jwt.PyJWK:
        # The current time.
        now = self._clock()
        # Keys are 'stale' if never downloaded or older than 10 minutes.
        stale = self._fetched_at is None or now - self._fetched_at > JWKS_TTL_SECONDS
        # May we refresh for an unknown key id? Only if the last download is over a minute
        #   old.
        may_refresh_for_kid = (
            self._fetched_at is None or now - self._fetched_at > UNKNOWN_KID_REFRESH_SECONDS
        )
        # Refresh if stale, or if this key id is unknown and we're allowed to refresh...
        if stale or (kid not in self._keys and may_refresh_for_kid):
            # ...keeping the old keys if the download fails and we have some.
            await self._refresh(keep_old_on_error=bool(self._keys))
        # Find the key with this id.
        key = self._keys.get(kid)
        # Still unknown after refreshing:
        if key is None:
            # reject the token.
            self._reject("unknown_kid")
        # Return the key.
        return key

    # Download Supabase's public keys. If that fails, keep using the old ones; with none at all,
    # refuse everything.
    async def _refresh(self, *, keep_old_on_error: bool) -> None:
        # Try to download the key set:
        try:
            # GET Supabase's public keys (5-second limit),
            r = await self._http.get(self._jwks_url, timeout=JWKS_TIMEOUT_SECONDS)
            # treat an error status (4xx/5xx) as a failure,
            r.raise_for_status()
            # and parse the keys.
            keyset = jwt.PyJWKSet.from_dict(r.json())
        # Network problem, bad JSON or bad keys:
        except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
            # log the kind of failure.
            structlog.get_logger().warning("auth.jwks_fetch_failed", error=type(exc).__name__)
            if keep_old_on_error:  # keep serving with the last good keys during a blip
                # Pretend we just refreshed, so we don't retry on every request...
                self._fetched_at = self._clock()
                # ...and stop here.
                return
            # No keys at all: we can't verify anything, so nothing gets in (fail closed).
            raise InfrastructureError("authentication is temporarily unavailable") from exc
        # Store the new keys by key id (keys without an id are ignored).
        self._keys = {k.key_id: k for k in keyset.keys if k.key_id}
        # Remember when we downloaded them.
        self._fetched_at = self._clock()

    # A static method doesn't need `self`.
    @staticmethod
    # Log why (without the token) and answer 401 'invalid or expired token'.
    def _reject(reason: str) -> NoReturn:
        # Log the reason (never the token itself).
        structlog.get_logger().info("auth.token_rejected", reason=reason)
        # Answer 401 with the vague message.
        raise AuthenticationError(_INVALID)

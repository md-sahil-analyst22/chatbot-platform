# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 Every way a login token can be wrong is refused (expired, wrong signer, wrong
#                algorithm...).
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""JwksTokenVerifier (ADR-0007): every way a token can be wrong must be refused (R16).

Real ES256 keys and real signatures; only the JWKS HTTP endpoint is simulated.
"""

# base64 — turns bytes into text and back.
import base64

# hashlib — fingerprints (hashes) such as SHA-256.
import hashlib

# hmac — signatures made with a shared secret, and safe comparison.
import hmac

# json — reads and writes JSON text.
import json

# time — clocks and timers.
import time

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# httpx — the HTTP client we use to call other web services.
import httpx

# jwt — PyJWT, reads and checks login tokens (JWTs).
import jwt

# pytest — the test framework.
import pytest

# From cryptography.hazmat.primitives — low-level crypto building blocks: serialization =
#   reads/writes keys in standard formats.
from cryptography.hazmat.primitives import serialization

# From cryptography.hazmat.primitives.asymmetric — public/private key crypto: ec =
#   elliptic-curve keys (used for ES256 test tokens).
from cryptography.hazmat.primitives.asymmetric import ec

# From saathi.platform.errors — our error types: AuthenticationError = 401 not logged in;
#   AuthorizationError = 403 role not allowed; InfrastructureError = our side broke.
from saathi.platform.errors import AuthenticationError, AuthorizationError, InfrastructureError

# From saathi.platform.security.auth — who is calling and what they may do: Membership = one
#   (workspace, role) pair; Role = viewer/agent/admin/owner.
from saathi.platform.security.auth import Membership, Role

# From saathi.platform.security.jwt_verifier — the login-token checker:
#   UNKNOWN_KID_REFRESH_SECONDS = how often unknown keys may trigger a refresh; JwksTokenVerifier
#   = the real login checker.
from saathi.platform.security.jwt_verifier import (
    UNKNOWN_KID_REFRESH_SECONDS,
    JwksTokenVerifier,
)

# The issuer our test tokens claim.
ISSUER = "https://proj.supabase.co/auth/v1"
# The audience our test tokens claim.
AUDIENCE = "authenticated"
# A random test tenant.
TENANT = uuid4()


# Helper: make a signing key pair with a key id.
def _keypair(kid: str) -> tuple[ec.EllipticCurvePrivateKey, dict[str, Any]]:
    # A new private key (ES256 = elliptic curve P-256).
    private = ec.generate_private_key(ec.SECP256R1())
    # Its public half in JWK format (what Supabase publishes).
    public_jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    # Return the private key and the public JWK labelled with the key id.
    return private, {**public_jwk, "kid": kid, "alg": "ES256", "use": "sig"}


# One key pair used by most tests.
KEY, JWK = _keypair("k1")


# Helper: build a signed test token; `overrides` change or (with None) remove claims.
def _token(key: Any = KEY, kid: str = "k1", alg: str = "ES256", **overrides: Any) -> str:
    # Current time in seconds.
    now = int(time.time())
    # Normal claims: user, issuer, audience, issued now, expires in 5 minutes.
    claims = {"sub": "user-1", "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300}
    # Apply the test's changes.
    claims.update(overrides)
    # Drop claims set to None (to test missing claims).
    claims = {k: v for k, v in claims.items() if v is not None}
    # Sign it with the given key, algorithm and key id.
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


# A fake membership lookup that also records who was looked up.
class FakeMemberships:
    # By default: one admin membership in TENANT.
    def __init__(self, rows: list[Membership] | None = None) -> None:
        # Use the given rows, or the default.
        self.rows = [Membership(TENANT, Role.ADMIN)] if rows is None else rows
        # User ids we were asked about.
        self.calls: list[str] = []

    # Answer a lookup.
    async def memberships(self, auth_user_id: str) -> list[Membership]:
        # Record the user id.
        self.calls.append(auth_user_id)
        # Return the rows.
        return self.rows


# A fake Supabase key endpoint that counts downloads and can be made to fail.
class Jwks:
    """Simulated JWKS endpoint that counts fetches and can fail."""

    # Start with these keys.
    def __init__(self, keys: list[dict[str, Any]]) -> None:
        # Keys, download count, and whether to fail.
        self.keys, self.fetches, self.fail = keys, 0, False

    # Answer one HTTP request.
    def handler(self, request: httpx.Request) -> httpx.Response:
        # Count it.
        self.fetches += 1
        # If told to fail...
        if self.fail:
            # ...answer 503 (down).
            return httpx.Response(503)
        # Otherwise answer with the keys.
        return httpx.Response(200, json={"keys": self.keys})


# A fake clock the test can move forward.
class Clock:
    # Start at time 1000.
    def __init__(self) -> None:
        # (the current time)
        self.now = 1000.0

    # Calling it returns the current time...
    def __call__(self) -> float:
        # ...as set by the test.
        return self.now


# Helper: build the real verifier wired to the fakes.
def _verifier(
    jwks: Jwks, memberships: FakeMemberships | None = None, clock: Clock | None = None
) -> JwksTokenVerifier:
    # The real verifier with:
    return JwksTokenVerifier(
        # an HTTP client whose requests go to the fake endpoint,
        httpx.AsyncClient(transport=httpx.MockTransport(jwks.handler)),
        # the key address,
        jwks_url="https://proj.supabase.co/auth/v1/.well-known/jwks.json",
        # the issuer,
        issuer=ISSUER,
        # the audience,
        audience=AUDIENCE,
        # the memberships (default: one admin),
        memberships=memberships or FakeMemberships(),
        # the clock (default: a new fake clock).
        clock=clock or Clock(),
    )


# A good token gives the caller from the membership lookup.
async def test_valid_token_gives_principal_from_membership() -> None:
    # Fake memberships.
    m = FakeMemberships()
    # Verify a good token.
    p = await _verifier(Jwks([JWK]), m).verify(_token())
    # User, tenant and role are right.
    assert (p.user_id, p.tenant_id, p.role) == ("user-1", TENANT, Role.ADMIN)
    # The membership was looked up for that user.
    assert m.calls == ["user-1"]


# Keys are downloaded once, not on every request.
async def test_keys_are_cached_between_requests() -> None:
    # A fake key endpoint.
    jwks = Jwks([JWK])
    # A verifier using it.
    v = _verifier(jwks)
    # First request.
    await v.verify(_token())
    # Second request.
    await v.verify(_token())
    # Only one download.
    assert jwks.fetches == 1


# Run once per bad token below (each with a readable test id):
@pytest.mark.parametrize(
    # the value each case provides,
    "token",
    # the cases:
    [
        # expired 2 minutes ago,
        pytest.param(_token(exp=int(time.time()) - 120), id="expired"),
        # wrong issuer,
        pytest.param(_token(iss="https://evil.example/auth/v1"), id="wrong-issuer"),
        # wrong audience,
        pytest.param(_token(aud="anon"), id="wrong-audience"),
        # no user id,
        pytest.param(_token(sub=None), id="missing-sub"),
        # no expiry,
        pytest.param(_token(exp=None), id="missing-exp"),
        # no issued-at,
        pytest.param(_token(iat=None), id="missing-iat"),
        # signed by a different key with the same key id,
        pytest.param(_token(key=_keypair("k1")[0]), id="signed-by-another-key"),
        # not a token at all,
        pytest.param("not-a-jwt", id="garbage"),
        # signature tampered with.
        pytest.param(_token()[:-4] + "AAAA", id="tampered-signature"),
    ],
)
# 🔒 Every bad token is refused.
async def test_bad_tokens_are_rejected(token: str) -> None:
    # Expect 401 (AuthenticationError) from the next line: (`exc` keeps the error)
    with pytest.raises(AuthenticationError) as exc:
        # verify the bad token,
        await _verifier(Jwks([JWK])).verify(token)
    assert exc.value.message == "invalid or expired token"  # generic: no hint to attackers


# 🔒 A classic attack: HS256 'signed' with our PUBLIC key must be refused.
async def test_hs256_forged_with_public_key_is_rejected() -> None:
    """Algorithm-confusion attack: HMAC-sign with the PUBLIC key as the shared secret.

    Built by hand, because PyJWT (rightly) refuses to create such a token.
    """
    # Our public key in PEM format (attackers can get it).
    public_pem = KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Helper: base64url without padding.
    def b64(data: bytes) -> bytes:
        # Encode.
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    # A header claiming HS256.
    header = b64(json.dumps({"alg": "HS256", "kid": "k1", "typ": "JWT"}).encode())
    # Now.
    now = int(time.time())
    # Claims pretending to be 'admin':
    payload = b64(
        # turned into JSON bytes:
        json.dumps(
            {"sub": "admin", "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300}
        ).encode()
    )
    # An HMAC 'signature' using the public key as the secret.
    signature = b64(hmac.new(public_pem, header + b"." + payload, hashlib.sha256).digest())
    # Join the three parts into a forged token.
    forged = (header + b"." + payload + b"." + signature).decode()
    # Expect 401 (AuthenticationError) from the next line:
    with pytest.raises(AuthenticationError):
        # verify the forged token.
        await _verifier(Jwks([JWK])).verify(forged)


# 🔒 An unsigned token (alg 'none') is refused.
async def test_unsigned_token_is_rejected() -> None:
    # Build a token with no signature.
    unsigned = jwt.encode({"sub": "admin", "iss": ISSUER, "aud": AUDIENCE}, None, algorithm="none")
    # Expect 401 (AuthenticationError) from the next line:
    with pytest.raises(AuthenticationError):
        # verify it.
        await _verifier(Jwks([JWK])).verify(unsigned)


# When Supabase adds a new key, it's picked up with one extra download.
async def test_rotated_key_is_picked_up_once() -> None:
    # A second key pair, 'k2'.
    new_key, new_jwk = _keypair("k2")
    # A fake endpoint (k1 only) and a fake clock.
    jwks, clock = Jwks([JWK]), Clock()
    # A verifier.
    v = _verifier(jwks, clock=clock)
    await v.verify(_token())  # caches k1
    jwks.keys = [JWK, new_jwk]  # Supabase rotates
    # Move the clock past the one-minute refresh limit.
    clock.now += UNKNOWN_KID_REFRESH_SECONDS + 1
    # A token signed with k2 now works...
    p = await v.verify(_token(key=new_key, kid="k2"))
    # ...for the right tenant...
    assert p.tenant_id == TENANT
    # ...after exactly one more download.
    assert jwks.fetches == 2


# 🔒 Attackers sending random key ids can't make us hammer Supabase.
async def test_random_kids_cannot_hammer_the_jwks_endpoint() -> None:
    # A fake endpoint.
    jwks = Jwks([JWK])
    # A verifier.
    v = _verifier(jwks)
    # First request (downloads keys).
    await v.verify(_token())
    # 20 tokens with made-up key ids:
    for i in range(20):
        # Expect 401 (AuthenticationError) from the next line:
        with pytest.raises(AuthenticationError):
            # verify it.
            await v.verify(_token(kid=f"random-{i}"))
    assert jwks.fetches == 1  # refresh for unknown kids is rate-limited


# 🔒 Supabase down and no cached keys -> refuse (fail closed).
async def test_jwks_down_with_no_cached_keys_fails_closed() -> None:
    # A fake endpoint...
    jwks = Jwks([JWK])
    # ...that is down.
    jwks.fail = True
    # Expect InfrastructureError from the next line:
    with pytest.raises(InfrastructureError):
        # verify a good token.
        await _verifier(jwks).verify(_token())


# A short Supabase outage doesn't log everyone out.
async def test_jwks_blip_keeps_using_cached_keys() -> None:
    # A fake endpoint and clock.
    jwks, clock = Jwks([JWK]), Clock()
    # A verifier.
    v = _verifier(jwks, clock=clock)
    # First request caches the keys.
    await v.verify(_token())
    # Now Supabase goes down.
    jwks.fail = True
    clock.now += 3600  # cache expired and refresh fails
    # The cached keys still work.
    assert (await v.verify(_token())).tenant_id == TENANT


# 🔒 A valid login without a workspace gets 403.
async def test_user_without_membership_is_forbidden() -> None:
    # Expect AuthorizationError from the next line:
    with pytest.raises(AuthorizationError):
        # verify with no memberships.
        await _verifier(Jwks([JWK]), FakeMemberships([])).verify(_token())


# 🔒 A user in two workspaces is refused, never guessed.
async def test_user_in_two_tenants_is_refused_not_guessed() -> None:
    # Two memberships.
    rows = [Membership(uuid4(), Role.OWNER), Membership(uuid4(), Role.VIEWER)]
    # Expect AuthorizationError from the next line:
    with pytest.raises(AuthorizationError):
        # verify.
        await _verifier(Jwks([JWK]), FakeMemberships(rows)).verify(_token())


# Invalid tokens never reach the membership lookup.
async def test_membership_is_not_looked_up_for_invalid_tokens() -> None:
    # Fake memberships.
    m = FakeMemberships()
    # Expect 401 (AuthenticationError) from the next line:
    with pytest.raises(AuthenticationError):
        # verify a token with the wrong audience.
        await _verifier(Jwks([JWK]), m).verify(_token(aud="anon"))
    # The lookup was never called.
    assert m.calls == []

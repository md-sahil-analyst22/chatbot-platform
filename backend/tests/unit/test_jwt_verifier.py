"""JwksTokenVerifier (ADR-0007): every way a token can be wrong must be refused (R16).

Real ES256 keys and real signatures; only the JWKS HTTP endpoint is simulated.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from saathi.platform.errors import AuthenticationError, AuthorizationError, InfrastructureError
from saathi.platform.security.auth import Membership, Role
from saathi.platform.security.jwt_verifier import (
    UNKNOWN_KID_REFRESH_SECONDS,
    JwksTokenVerifier,
)

ISSUER = "https://proj.supabase.co/auth/v1"
AUDIENCE = "authenticated"
TENANT = uuid4()


def _keypair(kid: str) -> tuple[ec.EllipticCurvePrivateKey, dict[str, Any]]:
    private = ec.generate_private_key(ec.SECP256R1())
    public_jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    return private, {**public_jwk, "kid": kid, "alg": "ES256", "use": "sig"}


KEY, JWK = _keypair("k1")


def _token(key: Any = KEY, kid: str = "k1", alg: str = "ES256", **overrides: Any) -> str:
    now = int(time.time())
    claims = {"sub": "user-1", "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": kid})


class FakeMemberships:
    def __init__(self, rows: list[Membership] | None = None) -> None:
        self.rows = [Membership(TENANT, Role.ADMIN)] if rows is None else rows
        self.calls: list[str] = []

    async def memberships(self, auth_user_id: str) -> list[Membership]:
        self.calls.append(auth_user_id)
        return self.rows


class Jwks:
    """Simulated JWKS endpoint that counts fetches and can fail."""

    def __init__(self, keys: list[dict[str, Any]]) -> None:
        self.keys, self.fetches, self.fail = keys, 0, False

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.fetches += 1
        if self.fail:
            return httpx.Response(503)
        return httpx.Response(200, json={"keys": self.keys})


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _verifier(
    jwks: Jwks, memberships: FakeMemberships | None = None, clock: Clock | None = None
) -> JwksTokenVerifier:
    return JwksTokenVerifier(
        httpx.AsyncClient(transport=httpx.MockTransport(jwks.handler)),
        jwks_url="https://proj.supabase.co/auth/v1/.well-known/jwks.json",
        issuer=ISSUER,
        audience=AUDIENCE,
        memberships=memberships or FakeMemberships(),
        clock=clock or Clock(),
    )


async def test_valid_token_gives_principal_from_membership() -> None:
    m = FakeMemberships()
    p = await _verifier(Jwks([JWK]), m).verify(_token())
    assert (p.user_id, p.tenant_id, p.role) == ("user-1", TENANT, Role.ADMIN)
    assert m.calls == ["user-1"]


async def test_keys_are_cached_between_requests() -> None:
    jwks = Jwks([JWK])
    v = _verifier(jwks)
    await v.verify(_token())
    await v.verify(_token())
    assert jwks.fetches == 1


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_token(exp=int(time.time()) - 120), id="expired"),
        pytest.param(_token(iss="https://evil.example/auth/v1"), id="wrong-issuer"),
        pytest.param(_token(aud="anon"), id="wrong-audience"),
        pytest.param(_token(sub=None), id="missing-sub"),
        pytest.param(_token(exp=None), id="missing-exp"),
        pytest.param(_token(iat=None), id="missing-iat"),
        pytest.param(_token(key=_keypair("k1")[0]), id="signed-by-another-key"),
        pytest.param("not-a-jwt", id="garbage"),
        pytest.param(_token()[:-4] + "AAAA", id="tampered-signature"),
    ],
)
async def test_bad_tokens_are_rejected(token: str) -> None:
    with pytest.raises(AuthenticationError) as exc:
        await _verifier(Jwks([JWK])).verify(token)
    assert exc.value.message == "invalid or expired token"  # generic: no hint to attackers


async def test_hs256_forged_with_public_key_is_rejected() -> None:
    """Algorithm-confusion attack: HMAC-sign with the PUBLIC key as the shared secret.

    Built by hand, because PyJWT (rightly) refuses to create such a token.
    """
    public_pem = KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    def b64(data: bytes) -> bytes:
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    header = b64(json.dumps({"alg": "HS256", "kid": "k1", "typ": "JWT"}).encode())
    now = int(time.time())
    payload = b64(
        json.dumps(
            {"sub": "admin", "iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300}
        ).encode()
    )
    signature = b64(hmac.new(public_pem, header + b"." + payload, hashlib.sha256).digest())
    forged = (header + b"." + payload + b"." + signature).decode()
    with pytest.raises(AuthenticationError):
        await _verifier(Jwks([JWK])).verify(forged)


async def test_unsigned_token_is_rejected() -> None:
    unsigned = jwt.encode({"sub": "admin", "iss": ISSUER, "aud": AUDIENCE}, None, algorithm="none")
    with pytest.raises(AuthenticationError):
        await _verifier(Jwks([JWK])).verify(unsigned)


async def test_rotated_key_is_picked_up_once() -> None:
    new_key, new_jwk = _keypair("k2")
    jwks, clock = Jwks([JWK]), Clock()
    v = _verifier(jwks, clock=clock)
    await v.verify(_token())  # caches k1
    jwks.keys = [JWK, new_jwk]  # Supabase rotates
    clock.now += UNKNOWN_KID_REFRESH_SECONDS + 1
    p = await v.verify(_token(key=new_key, kid="k2"))
    assert p.tenant_id == TENANT
    assert jwks.fetches == 2


async def test_random_kids_cannot_hammer_the_jwks_endpoint() -> None:
    jwks = Jwks([JWK])
    v = _verifier(jwks)
    await v.verify(_token())
    for i in range(20):
        with pytest.raises(AuthenticationError):
            await v.verify(_token(kid=f"random-{i}"))
    assert jwks.fetches == 1  # refresh for unknown kids is rate-limited


async def test_jwks_down_with_no_cached_keys_fails_closed() -> None:
    jwks = Jwks([JWK])
    jwks.fail = True
    with pytest.raises(InfrastructureError):
        await _verifier(jwks).verify(_token())


async def test_jwks_blip_keeps_using_cached_keys() -> None:
    jwks, clock = Jwks([JWK]), Clock()
    v = _verifier(jwks, clock=clock)
    await v.verify(_token())
    jwks.fail = True
    clock.now += 3600  # cache expired and refresh fails
    assert (await v.verify(_token())).tenant_id == TENANT


async def test_user_without_membership_is_forbidden() -> None:
    with pytest.raises(AuthorizationError):
        await _verifier(Jwks([JWK]), FakeMemberships([])).verify(_token())


async def test_user_in_two_tenants_is_refused_not_guessed() -> None:
    rows = [Membership(uuid4(), Role.OWNER), Membership(uuid4(), Role.VIEWER)]
    with pytest.raises(AuthorizationError):
        await _verifier(Jwks([JWK]), FakeMemberships(rows)).verify(_token())


async def test_membership_is_not_looked_up_for_invalid_tokens() -> None:
    m = FakeMemberships()
    with pytest.raises(AuthenticationError):
        await _verifier(Jwks([JWK]), m).verify(_token(aud="anon"))
    assert m.calls == []

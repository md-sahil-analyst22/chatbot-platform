# ADR-0007: Supabase JWT verification and tenant membership (P1.7)

- **Status:** Accepted
- **Date:** 2026-11-15
- **Deciders:** Sahil

## Context
ADR-0002 chose Supabase Auth. Every `/api/v1` request carries a Supabase access token. R8 says
the tenant comes from the verified token, never from the request. Supabase tokens identify the
**user** (`sub`); they don't carry our tenant or role. `user_accounts` (migration 0002) maps a
user to a tenant and role, but it is under RLS, so it can't be read before the tenant is known.

## Problem
1. Verify tokens correctly: signature, algorithm, issuer, audience and expiry, with no network
   call per request and no blocking I/O (R32).
2. Turn a verified user into exactly one `(tenant_id, role)` without trusting anything the
   client sends.
3. Fail closed on every error (R16).

## Decision
1. **Signature:** verify with Supabase's **JWKS** (`AUTH_JWKS_URL`).
   - Allowed algorithms: **ES256 and RS256** only. HS256 and `none` are rejected, so the public key can never be used as an HMAC secret.
   - Keys are fetched with the shared async HTTP client (R11) and cached for 10 minutes.
   - A token with an unknown `kid` triggers at most one refresh per 60 seconds, so random `kid`s can't be used to hammer Supabase.
2. **Claims:**
   - `iss` must equal `AUTH_ISSUER`; `aud` must contain `AUTH_AUDIENCE` (`authenticated`).
   - `exp`, `iat` and `sub` are required, with 30 seconds of clock leeway.
3. **Membership:** a narrow `SECURITY DEFINER` function, `resolve_user_membership(auth_user_id)`, returns only `(tenant_id, role)` rows for that user. It's the same pattern as `resolve_bot_public_key()` (migration 0003).
   - Exactly one membership is required. Zero memberships → 403. More than one → 403, until tenant switching is designed.
   - The role comes from the database on every request, so removing a user or changing a role applies immediately; we don't wait for a token to expire.
4. **Wiring:**
   - The verifier is a platform adapter (`platform/security/jwt_verifier.py`).
   - Membership is a port (`MembershipLookup`), implemented by the tenancy module and connected in `bootstrap/` (R1, R4, R6).
5. **Configuration:**
   - If all three `AUTH_*` values are set, the verifier is active.
   - In `staging` or `production`, a missing value **stops the app from starting**.
   - In `local` or `test` without them, `/api/v1` returns 401 (fail closed, as before).

## Alternatives considered
- **Tenant and role as custom JWT claims (Supabase Custom Access Token Hook).** No database
  lookup per request, but a role change waits up to an hour for the token to refresh, and it
  needs dashboard configuration outside the repo. Revisit if the lookup shows up in latency numbers.
- **`X-Tenant-ID` header chosen by the client.** Rejected: it breaks R8, even if checked against
  memberships later.
- **Fetching JWKS on every request, or with PyJWT's `PyJWKClient`.** Rejected: a network call per request, and
  `PyJWKClient` uses blocking `urllib`.

## Advantages
- One indexed query per request. Role changes are immediate. No extra infrastructure.
- Verification happens locally after the first JWKS fetch.

## Disadvantages
- One database round trip per authenticated request (about 1 ms on the same region). It can be
  cached in Redis later; the cache must be invalidated on membership changes.
- A user who belongs to two tenants is refused until tenant switching is designed.

## Security impact
- Algorithm allowlist, issuer, audience, expiry and `sub` are all enforced.
- Generic messages are returned to clients; the exact reason is logged without the token (R17, R18).
- The function returns only ids and roles. `anon` and `authenticated` can't execute it (Supabase Data API).

## Performance impact
- After warm-up, JWT verification is CPU-only (ES256 verify: tens of microseconds), plus one
  primary-key-sized index lookup (`ix_user_accounts_auth_user_id`).

## Operational impact
- If JWKS is unreachable with no cached keys, requests fail (500, logged), never pass.
- Supabase key rotation is handled by the unknown-`kid` refresh.

## Consequences
- The first tenant and owner are created by an operator, as described in the local-setup runbook,
  until self-service sign-up exists.

## Revisit when
- Users need several tenants (tenant switcher).
- Auth lookups exceed 5% of p95 request time.

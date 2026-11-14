# ADR-0004: Storing tenants' own provider API keys (BYOK)

- **Status:** Proposed - design accepted now, feature ships in Phase 8.1 (Pro tier)
- **Date:** 2026-11-12
- **Deciders:** Sahil

## Context
Some tenants (agencies, larger businesses) want their own LLM provider account so usage is billed
to them. Most launch customers (CA firms, clinics) will not have provider keys and are better
served by platform-managed keys with usage included in the plan.

## Problem
Storing customer secrets makes the platform a high-value target. A leak, a cross-tenant mix-up, or
a key printed in a log would be a serious incident.

## Decision
- Separate `credentials` module (own security profile; candidate for its own service).
- **AES-256-GCM** with key ids (`v1.<kid>.<nonce>.<ciphertext>`); master keys from the hosting
  secret store (`CREDENTIALS_ENCRYPTION_KEYS`), first key encrypts, all keys decrypt (rotation).
- **Associated data** `tenant:<id>:provider:<name>` binds each ciphertext to its owner.
- **Write-only API:** keys are never returned; the UI shows `••••abcd`.
- Validate with one provider call before storing; one active key per tenant + provider (partial
  unique index); previous key revoked on replacement.
- OWNER role only to add, rotate or revoke; ADMIN may see the masked list; every change audited.
- Keys never logged, traced (Langfuse), or included in error messages.
- Resolution order at request time: tenant key → platform key only if the plan allows fallback →
  otherwise fail closed with a clear configuration error.

## Alternatives
- Cloud KMS envelope encryption (AWS KMS / GCP KMS / Azure Key Vault): stronger key custody;
  adopt when moving off Railway/Render or when a client requires it.
- HashiCorp Vault: operationally heavy for a solo team.

## Advantages
Simple, testable, rotation-ready, no plaintext at rest, cross-tenant swaps detected cryptographically.

## Disadvantages
Master keys live in the app's environment; a full app compromise exposes them (KMS reduces this).

## Security impact
Introduces a new secret class; mitigated by encryption, AAD binding, least privilege, auditing.

## Performance impact
Decryption is microseconds; resolved keys can be cached in process memory for a short TTL.

## Operational impact
Key rotation runbook: add new key first in the list, re-encrypt rows where `needs_rotation`, then
remove the old key.

## Consequences
LLM cost attribution changes for BYOK tenants; usage caps still apply to protect the platform.

## Revisit when
A client requires customer-managed keys, or the platform moves to a cloud with managed KMS.

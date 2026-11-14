# modules/credentials (Phase 8, Pro tier)

Tenants' own provider API keys ("bring your own key"). Designed and scaffolded now; the Studio
screen and endpoints ship in Phase 8.1.

| Rule | How |
|---|---|
| Encrypted at rest | AES-256-GCM via `platform/security/crypto.py`, master keys in the hosting secret store |
| Bound to owner | Associated data `tenant:<id>:provider:<name>`: a ciphertext moved to another row fails |
| Write-only | API returns `••••a1b2` only, never the key |
| Validated on save | One cheap provider call before storing |
| Least privilege | Only OWNER can add, rotate or revoke; ADMIN can see masked list |
| Never leaked | Not logged, not traced, not returned in errors |
| Auditable | Every add / revoke recorded in the audit log |

| Layer | File |
|---|---|
| domain | `credential.py` - `ProviderCredential`, status, masking |
| ports | `vault.py` - `SecretCipher`, `CredentialRepository`, `KeyValidator` |
| application | `services.py` - save, list, revoke, resolve for a tenant |
| adapters | `orm.py` - `provider_credentials` table (added to migrations in Phase 8) |
| api | `routes.py` - planned endpoints (not mounted yet) |

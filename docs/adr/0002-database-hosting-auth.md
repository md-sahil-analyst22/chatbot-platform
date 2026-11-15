# ADR-0002: Postgres host, app hosting and auth provider

- **Status:** Accepted for Postgres, auth and storage (2026-11-14). App hosting: superseded by
  ADR-0008 (Hostinger VPS, 2026-11-15).
- **Deciders:** Sahil

## Context
P0.1 lists "Supabase (or Neon)", "Railway/Render" and P1.7 "Supabase Auth / Clerk".
These must be fixed before Phase 1, because auth affects how RLS gets `tenant_id` (P1.6).

## Options

| Concern | Option A | Option B | Notes |
|---|---|---|---|
| Postgres + pgvector | Supabase | Neon | Supabase bundles Auth + Storage; Neon has branching for previews |
| Auth | Supabase Auth | Clerk | Supabase Auth is simplest if the DB is Supabase |
| Object storage | Supabase Storage | Cloudflare R2 | |
| App hosting | Railway | Render | |
| Data region | Verify at signup | | DPDP: prefer an India region for client data where offered |

## Decision
**Supabase** for Postgres + pgvector, Auth and Storage, in an India region if one is offered.
App hosting: decided in ADR-0008 (Hostinger VPS, Mumbai). Keep the app stateless so
hosting can change later without code changes.

### How the code uses Supabase
- **Database:** the app connects as `saathi_app` (NOBYPASSRLS, R24); migrations connect as the
  schema owner. Use the **session pooler (port 5432)** or the direct connection. The transaction
  pooler (6543) breaks asyncpg prepared statements. On Supabase, create `saathi_app` once by
  running `infra/postgres/init/02_app_role.sh`'s SQL in the SQL editor (the Docker init script
  only runs locally), and enable the `vector` extension.
- **Auth:** the token verifier (ADR-0007) reads `AUTH_JWKS_URL`
  (`https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`), `AUTH_ISSUER`
  (`https://<ref>.supabase.co/auth/v1`) and `AUTH_AUDIENCE` (`authenticated`).
- **Storage:** `platform/storage/supabase_store.py` (`STORAGE_PROVIDER=supabase`) uses a private
  bucket for raw uploads and a public bucket for logos, with the server-only service-role key.
  Keys must start with `t/{tenant_id}/`.

## Revisit when
First client with data-residency or enterprise SSO requirements.

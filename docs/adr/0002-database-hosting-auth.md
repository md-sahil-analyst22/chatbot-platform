# ADR-0002: Postgres host, app hosting and auth provider

- **Status:** Proposed - **decide by Sun 15 Nov 2026 (end of Phase 0)**
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

## Recommendation (to confirm)
Supabase (Postgres + Auth + Storage, India region if available) + Railway or Render (nearest
available region). Keep the app stateless so hosting can change later without code changes.

## Revisit when
First client with data-residency or enterprise SSO requirements.

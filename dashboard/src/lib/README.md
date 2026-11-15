# src/lib/

Framework-level helpers shared by every feature. No screens here.

- `api/` - typed API client (`client.ts`) and DTO types mirroring the backend (`types.ts`)
- `auth/` - access-token holder; the Supabase Auth / Clerk SDK plugs in at P1.7

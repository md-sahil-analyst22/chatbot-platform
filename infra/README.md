# infra/

| Path | Purpose |
|---|---|
| `docker-compose.yml` | Local stack: redis, api, worker (database = Supabase from `.env`); optional local postgres (`local-db` profile) and n8n |
| `postgres/init/` | Local Postgres only: runs once on an empty volume (extensions + least-privilege app role). On Supabase, run the same SQL in the SQL Editor (ADR-0002) |
| `docker-compose.prod.yml` | Production stack on the VPS: api, worker, redis (Postgres = Supabase); plus Bot Studio, routed by the server's existing Traefik via labels; released by hand: `saathi up -d --build` (ADR-0008) |
| `deploy/` | Hosting notes / platform config (decided in ADR-0002) |

All ports bind to `127.0.0.1` so local services are never exposed on your LAN.

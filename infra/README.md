# infra/

| Path | Purpose |
|---|---|
| `docker-compose.yml` | Local stack: redis, api, worker (database = Supabase from `.env`); optional local postgres (`local-db` profile) and n8n |
| `postgres/init/` | Local Postgres only: runs once on an empty volume (extensions + least-privilege app role). On Supabase, run the same SQL in the SQL Editor (ADR-0002) |
| `docker-compose.prod.yml` | Production stack on the VPS: api, worker, redis (Postgres = Supabase); released by hand on the server: `saathi up -d --build` (ADR-0008) |
| `nginx/saathi.conf.template` | nginx site for `api.<domain>` + `app.<domain>`, rendered and installed by `scripts/vps/setup.sh`; certbot adds HTTPS |
| `deploy/` | Hosting notes / platform config (decided in ADR-0002) |

All ports bind to `127.0.0.1` so local services are never exposed on your LAN.

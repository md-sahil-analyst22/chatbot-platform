# Runbook: local setup

1. Install: Docker Desktop, uv, Node 20, pre-commit.
2. `cp .env.example .env` and fill values: `DATABASE_URL` / `MIGRATION_DATABASE_URL` (Supabase session
   pooler, see ADR-0002; create the `saathi_app` role in the Supabase SQL Editor first), `SUPABASE_*`, keys.
   Offline instead: set `POSTGRES_OWNER_PASSWORD` / `APP_DB_PASSWORD`, point both URLs at the local
   Postgres and use `make up-local-db`.
3. `pre-commit install`
4. `make up` then `make ps` - redis must be `healthy` (and postgres, with `make up-local-db`).
5. `make migrate`
6. Open http://localhost:8000/health -> `{"status":"ok"}`.
7. Open http://localhost:8000/ready -> `{"status":"ready","checks":{"database":"ok","redis":"ok"}}`.
   A `503` names the failing dependency (`"fail"`); see `make logs` for `readiness.check_failed`.

## Troubleshooting
- **Port 5432 in use** - a local Postgres is running; stop it or change the host port in `infra/docker-compose.yml`.
- **Changed `APP_DB_PASSWORD` after first start** - init scripts run only on an empty volume:
  `docker compose --env-file .env -f infra/docker-compose.yml down -v` (deletes local data).

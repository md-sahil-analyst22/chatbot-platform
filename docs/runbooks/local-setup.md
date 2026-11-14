# Runbook: local setup

1. Install: Docker Desktop, uv, Node 20, pre-commit.
2. `cp .env.example .env` and fill values (`POSTGRES_OWNER_PASSWORD`, `APP_DB_PASSWORD`, keys).
3. `pre-commit install`
4. `make up` then `make ps` - postgres and redis must be `healthy`.
5. `make migrate`
6. Open http://localhost:8000/health -> `{"status":"ok"}`.

## Troubleshooting
- **Port 5432 in use** - a local Postgres is running; stop it or change the host port in `infra/docker-compose.yml`.
- **Changed `APP_DB_PASSWORD` after first start** - init scripts run only on an empty volume:
  `docker compose --env-file .env -f infra/docker-compose.yml down -v` (deletes local data).

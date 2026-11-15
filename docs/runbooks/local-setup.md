# Runbook: local setup

1. Install: Docker Desktop, uv, Node 24 LTS (20 is end-of-life), pre-commit.
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

## Create the first workspace (tenant) and owner

Until self-service sign-up exists (ADR-0007), an operator creates them once in the **Supabase SQL Editor**
(runs as the owner, so row-level security doesn't block it):

1. Sign up the user in Supabase Auth (Authentication -> Users -> Add user) and copy their **User UID**.
2. Run, with your values:
   ```sql
   with t as (insert into tenants (name, plan) values ('My Company', 'starter') returning id)
   insert into user_accounts (tenant_id, auth_user_id, email, role)
   select id, '<user-uid>', 'owner@example.com', 'owner' from t;
   ```
3. Log in from Bot Studio; `/api/v1` requests now resolve to that tenant with the `owner` role.

## Real-Postgres tests (`make test-db`)

Row-level security, the SQL repositories and the migration round trip need a real, **throwaway** Postgres 16+
with pgvector (never Supabase). One-time setup on that server:

```sql
CREATE ROLE saathi_owner LOGIN SUPERUSER PASSWORD 'owner-test';
CREATE ROLE saathi_app   LOGIN PASSWORD 'app-test' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE saathi_test OWNER saathi_owner;
```

Then:

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://saathi_owner:owner-test@127.0.0.1:5432/saathi_test
export TEST_APP_DATABASE_URL=postgresql+asyncpg://saathi_app:app-test@127.0.0.1:5432/saathi_test
make test-db
```

The suite migrates the database up, all the way down and up again, and empties every table before each test.

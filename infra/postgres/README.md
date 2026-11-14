# infra/postgres/

`init/` scripts run **once**, when the local data volume is empty:

| Script | Does |
|---|---|
| `01_extensions.sql` | `CREATE EXTENSION vector` |
| `02_app_role.sh` | Creates `saathi_app` (NOSUPERUSER, NOBYPASSRLS, DML-only) |

Two roles, on purpose:
- `saathi_owner` owns tables and runs Alembic migrations (`MIGRATION_DATABASE_URL`).
- `saathi_app` is what the API/worker use (`DATABASE_URL`). Because it is not the owner and
  cannot bypass RLS, Row-Level Security policies actually apply to it.

Schema changes never go here - they go in `backend/migrations/`.

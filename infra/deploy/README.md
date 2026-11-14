# Deployment

Decided in `docs/adr/0002-database-hosting-auth.md`.

## Services per environment
| Service | Image / command | Scaling unit |
|---|---|---|
| api | `backend/Dockerfile`, default CMD | requests/sec, concurrent SSE streams |
| worker | same image, `arq saathi.worker.WorkerSettings` | ingestion queue depth |
| postgres | managed (Supabase/Neon) | connections, storage |
| redis | managed (Upstash) | ops/sec |

## Rules
- Secrets only in the platform's variable store. Never bake them into the image.
- Run `alembic upgrade head` as a release/pre-deploy step using `MIGRATION_DATABASE_URL`.
- Set `FORWARDED_ALLOW_IPS` to the platform's proxy range, not `*`.
- Staging deploys automatically from `main`; production from tags (Phase 6).

# Deployment

Decided in `docs/adr/0002-database-hosting-auth.md` (Supabase) and `docs/adr/0008-hostinger-vps-hosting.md`
(Hostinger VPS + nginx). Step-by-step: `docs/runbooks/vps-deploy.md`.

## Services per environment
| Service | Image / command | Scaling unit |
|---|---|---|
| api | `backend/Dockerfile` via `infra/docker-compose.prod.yml`, behind host nginx | requests/sec, concurrent SSE streams |
| worker | same image, `arq saathi.worker.WorkerSettings` | ingestion queue depth |
| bot studio | static build served by nginx from `/var/www/saathi-studio` | bandwidth |
| postgres | managed (Supabase) | connections, storage |
| redis | container on the VPS (private network, AOF, `noeviction`) | ops/sec, memory |

## Rules
- Secrets only in `/home/deploy/chatbot-platform/.env` on the server (mode 600). Never in git or the image.
- `saathi up -d --build` runs `alembic upgrade head` as a one-shot job (`migrate` service); the API and worker start only after it succeeds.
- `FORWARDED_ALLOW_IPS` is the fixed Docker gateway (`172.30.0.1`), where host nginx's connections appear from. Never `*`.
- Probes: liveness `GET /health` (restart if failing; also the Docker `HEALTHCHECK`), readiness
  `GET /ready` (database + Redis; route traffic only when 200). Uptime monitors use `/health`.
- Releases are manual on the server: `saathi down` (optional) → `git pull` → `saathi up -d --build` (ADR-0008). Pull only commits that passed CI. Tag-based releases and a staging server: Phase 6.

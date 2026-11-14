# infra/

| Path | Purpose |
|---|---|
| `docker-compose.yml` | Local stack: postgres (pgvector), redis, api, worker, optional n8n |
| `postgres/init/` | Runs once on an empty volume: extensions + least-privilege app role |
| `nginx/` | Reverse-proxy config for the VPS stage (Phase 8+); not used on Railway/Render |
| `deploy/` | Hosting notes / platform config (decided in ADR-0002) |

All ports bind to `127.0.0.1` so local services are never exposed on your LAN.

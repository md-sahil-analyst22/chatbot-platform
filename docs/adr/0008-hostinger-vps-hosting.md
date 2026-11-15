# ADR-0008: Host the API, worker and Bot Studio on a Hostinger VPS (P1.10)

- **Status:** Accepted
- **Date:** 2026-11-15
- **Deciders:** Sahil
- **Supersedes:** the "Railway or Render" part of ADR-0002 (Supabase for DB, auth and storage stays)

## Context
ADR-0002 left app hosting open between Railway and Render, due 15 Nov 2026. The stack plan
(`02_ARCHITECTURE_AND_STACK.md`) listed Railway/Render for the MVP and "a Hetzner/AWS VPS" for
the scale stage. The product owner chose a **Hostinger VPS** (India / Mumbai, Ubuntu 24.04) now,
with nginx as reverse proxy and a custom domain.

## Decision
- **One VPS** runs everything except the database:
  - `docker compose -f infra/docker-compose.prod.yml` starts the API, the worker and Redis;
  - **host nginx** terminates TLS (Let's Encrypt via certbot);
  - nginx proxies `api.<base>` to the API on `127.0.0.1:8000`;
  - nginx serves the built Bot Studio at `app.<base>`.
  - `<base>` is a project sub-domain such as `saathi.yourdomain.com`, so the same domain can host
    other projects (`api.saathi.yourdomain.com`, `app.saathi.yourdomain.com`).
- **Postgres, Auth and Storage** stay on **Supabase** (ADR-0002).
- **Releases are manual, by the operator, on the server** (product owner's choice: no CI system gets
  access to the server). As the non-root `deploy` user: `saathi down` (optional) → `git pull` →
  `saathi up -d --build`. `up` does the whole release:
  1. builds the backend and Bot Studio images;
  2. runs migrations as a one-shot job (R25); the API and worker start only if it succeeds;
  3. starts Redis, the API and the worker;
  4. publishes Bot Studio to nginx's folder (one-shot job, no network).
- **Server hardening** is scripted in `scripts/vps/setup.sh`:
  - SSH keys only, with root login disabled;
  - `ufw` firewall allowing 22, 80 and 443 only;
  - `fail2ban` and unattended security upgrades;
  - Docker ports bound to localhost only.
- **Secrets** live only in `/home/deploy/chatbot-platform/.env` on the server (mode 600), never in git
  or the image (R17). GitHub holds no server credentials at all.

## Alternatives considered
- **Railway / Render:** zero server administration and built-in TLS and deploys, but a higher monthly
  cost for an always-on API + worker + Redis, and less control.
- **Containerised nginx:** one fewer host package, but certbot renewal and logs are harder for a
  first-time operator. Host nginx and certbot are the most widely documented path.

## Advantages
- Low, predictable cost. Full control. A Mumbai region is close to users and fits the data-residency
  preference in ADR-0002.

## Disadvantages
- **We are the operators:** OS patching (automated), disk and backup monitoring, TLS renewal
  (automated by certbot), and incident response.
- **Single server:** a VPS outage takes the API down. No zero-downtime deploys yet: a restart drops
  open connections for a few seconds (the whole build time if the operator runs `down` first).
- **Manual releases** depend on the operator remembering to pull only green (CI-passed) commits.
- **Latency to the database:** the API in Mumbai talks to Supabase in Singapore, adding about 60 ms
  per round trip. Move the Supabase project to Mumbai (`ap-south-1`) while it's still empty.

## Security impact
- Only nginx is reachable from the internet. The API, worker and Redis are on a private Docker
  network, with the API published on `127.0.0.1` only.
- uvicorn trusts `X-Forwarded-*` only from the fixed Docker gateway (`FORWARDED_ALLOW_IPS`), so
  clients can't spoof their IP. nginx overwrites the headers.
- The deploy user can run Docker. Docker access is root-equivalent, so the operator's SSH key must be
  protected like a root key. No CI system holds a key to the server.
- HSTS, `nosniff`, a referrer policy and `server_tokens off` are set on both sites.

## Operational impact
- First-time setup is about one hour, following `docs/runbooks/vps-deploy.md`.
- Rollback: `git checkout <last-good-commit>` and `saathi up -d --build` on the server.
  Never run a data-destroying `alembic downgrade` in production (R25).

## Revisit when
- One VPS can't handle the load (measure p95 latency and CPU), we need zero-downtime deploys, or a
  client needs an uptime SLA. Next step: two VPSs behind a load balancer, or a managed container service.

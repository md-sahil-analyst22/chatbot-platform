# ADR-0008: Host the API, worker and Bot Studio on a Hostinger VPS (P1.10)

- **Status:** Accepted (amended 2026-11-17: the existing Traefik replaces host nginx)
- **Date:** 2026-11-15
- **Deciders:** Sahil
- **Supersedes:** the "Railway or Render" part of ADR-0002 (Supabase for DB, auth and storage stays)

## Context
ADR-0002 left app hosting open between Railway and Render, due 15 Nov 2026. The stack plan
(`02_ARCHITECTURE_AND_STACK.md`) listed Railway/Render for the MVP and "a Hetzner/AWS VPS" for
the scale stage. The product owner chose a **Hostinger VPS** (India / Mumbai, Ubuntu 24.04) now,
with nginx as reverse proxy and a custom domain.

**Amendment (2026-11-17).** The VPS was bought with Hostinger's **n8n template**, which already runs
**Traefik** on ports 80/443 (host network, Docker provider, entrypoint `websecure`, cert resolver
`letsencrypt`) in front of n8n, which the product owner needs. Host nginx can't bind 80/443 next to
it, and replacing Traefik would take n8n offline. So the existing Traefik is the edge for Saathi too.
nginx remains, inside the Bot Studio container, serving static files.

## Decision
- **One VPS** runs everything except the database:
  - `docker compose -f infra/docker-compose.prod.yml` starts the API, the worker and Redis;
  - the server's **existing Traefik** terminates TLS and gets/renews Let's Encrypt certificates;
  - Saathi's containers carry Traefik labels: `api.<base>` → the API (port 8000), `app.<base>` →
    the Bot Studio container (non-root nginx serving the static build, port 8080);
  - Traefik only routes containers labelled `traefik.enable=true`. Nothing in Saathi's files stops,
    reconfigures or restarts Traefik or n8n.
  - `<base>` is a project sub-domain such as `saathi.yourdomain.com`, so the same domain can host
    other projects (`api.saathi.yourdomain.com`, `app.saathi.yourdomain.com`).
- **Postgres, Auth and Storage** stay on **Supabase** (ADR-0002).
- **Releases are manual, by the operator, on the server** (product owner's choice: no CI system gets
  access to the server). As the non-root `deploy` user: `saathi down` (optional) → `git pull` →
  `saathi up -d --build`. `up` does the whole release:
  1. builds the backend and Bot Studio images;
  2. runs migrations as a one-shot job (R25); the API and worker start only if it succeeds;
  3. starts Redis, the API, the worker and Bot Studio;
  4. Traefik picks up the labelled containers and issues certificates.
- **One setting:** `SAATHI_BASE_DOMAIN` in `.env`; the Studio's API URL, CORS origin and Traefik
  host rules are all derived from it.
- **Server hardening** is scripted in `scripts/vps/setup.sh`:
  - SSH keys only, with root login disabled;
  - `ufw` firewall allowing 22, 80 and 443 only;
  - `fail2ban` and unattended security upgrades;
  - Saathi publishes no public ports (the API is on `127.0.0.1:8000` for debugging only);
  - a readiness check that Traefik has the Docker provider, `websecure` and `letsencrypt`.
  - It removes a host nginx/certbot left by its earlier version, only if nginx isn't running.
- **Secrets** live only in `/home/deploy/chatbot-platform/.env` on the server (mode 600), never in git
  or the image (R17). GitHub holds no server credentials at all.

## Alternatives considered
- **Railway / Render:** zero server administration and built-in TLS and deploys, but a higher monthly
  cost for an always-on API + worker + Redis, and less control.
- **Host nginx + certbot** (the original choice): impossible next to the template's Traefik
  without moving Traefik (and n8n) to other ports, i.e. one proxy behind another.
- **Replace Traefik with nginx:** takes n8n offline and means re-doing Hostinger's n8n setup.
- **nginx container behind Traefik for the API:** a second proxy with no benefit; Traefik already
  provides TLS, headers and rate limiting.

## Advantages
- Low, predictable cost. Full control. A Mumbai region is close to users and fits the data-residency
  preference in ADR-0002.

## Disadvantages
- **We are the operators:** OS patching (automated), disk and backup monitoring, TLS renewal
  (automated by Traefik), and incident response.
- **Shared edge:** Saathi depends on Hostinger's Traefik (`traefik:latest`, managed in
  `/docker/traefik`). If someone changes its entrypoint or resolver names, Saathi's labels must
  follow (`setup.sh` checks them). Its image tag isn't pinned (outside this repo). Traefik mounts
  `/var/run/docker.sock`; when Docker restarts (e.g. a Docker package update) the mount goes stale
  and Traefik stops routing every site, n8n included, until it's restarted. `setup.sh` restarts it
  when Docker restarted during its run or Traefik's log shows the lost connection.
- **No request-body size limit at the edge yet:** Traefik's buffering middleware would also buffer
  streaming responses (SSE, P3.8), so uploads rely on the app's own size checks (R19).
- **Single server:** a VPS outage takes the API down. No zero-downtime deploys yet: a restart drops
  open connections for a few seconds (the whole build time if the operator runs `down` first).
- **Manual releases** depend on the operator remembering to pull only green (CI-passed) commits.
- **Latency to the database:** the API in Mumbai talks to Supabase in Singapore, adding about 60 ms
  per round trip. Move the Supabase project to Mumbai (`ap-south-1`) while it's still empty.

## Security impact
- Only Traefik is reachable from the internet (ports 80/443). Redis has no ports; the API is on
  `127.0.0.1` only; Bot Studio sits on its own network and can't reach Redis or the API container.
- uvicorn trusts `X-Forwarded-*` only from the fixed Docker gateway (`FORWARDED_ALLOW_IPS`), which is
  where Traefik's (host-network) connections arrive from, so clients can't spoof their IP. Traefik
  doesn't trust client-sent forwarding headers by default.
- Per-IP rate limit (20 req/s, burst 40) on the API at Traefik.
- The deploy user can run Docker. Docker access is root-equivalent, so the operator's SSH key must be
  protected like a root key. No CI system holds a key to the server.
- HSTS on both sites; `nosniff` and a referrer policy on the API; Bot Studio adds a strict CSP,
  `X-Frame-Options: DENY` and `server_tokens off`.
- The template also publishes n8n directly on a high port over plain HTTP (Docker bypasses ufw).
  Not Saathi's file, but worth closing (runbook "Recommended soon").

## Operational impact
- First-time setup is about 45 minutes, following `docs/runbooks/vps-deploy.md`.
- Rollback: `git checkout <last-good-commit>` and `saathi up -d --build` on the server.
  Never run a data-destroying `alembic downgrade` in production (R25).

## Revisit when
- One VPS can't handle the load (measure p95 latency and CPU), we need zero-downtime deploys, or a
  client needs an uptime SLA. Next step: two VPSs behind a load balancer, or a managed container service.

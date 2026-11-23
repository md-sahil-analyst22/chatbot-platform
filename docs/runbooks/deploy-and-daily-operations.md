# Saathi: deploy and daily operations guide

A plain-language guide for running Saathi day to day: working on your Mac, releasing to the server,
and keeping it healthy. Every command here was used on this project's real setup.

> First-time setup of a **new** server is in [`vps-deploy.md`](vps-deploy.md). This guide is for
> after that: releasing, checking and fixing.

---

## 1. Your setup at a glance

| What | Where / value |
|---|---|
| Bot Studio (dashboard) | https://app.saathi.sahil-aisolution.cloud |
| API | https://api.saathi.sahil-aisolution.cloud (health check: `/health`) |
| Server | Hostinger VPS (n8n template), logged in as `root` |
| Project folder on the server | `~/Projects/chatbot-platform` (full path `/root/Projects/chatbot-platform`) |
| Server settings file | `~/Projects/chatbot-platform/.env` (secret, never in git) |
| Front door + HTTPS | **Traefik**, shared with your **n8n** (don't stop or change it) |
| Database, login, file storage | **Supabase** (managed; not on the server) |
| Code | GitHub, branch `main` |
| Project folder on your Mac | `~/Projects/chatbot-platform` |

```
Your Mac ──git push──> GitHub (CI checks) ──you run "git pull" on the server──> VPS
Browser ──HTTPS──> Traefik ─┬─ app.saathi.sahil-aisolution.cloud ──> Bot Studio
                            ├─ api.saathi.sahil-aisolution.cloud ──> API ──> Supabase
                            └─ your n8n address ──────────────────> n8n
```

**Where to type:** 💻 = your Mac's Terminal (VS Code: Terminal → New Terminal) ·
🖥️ = on the server (after logging in, see section 3.1).

> ⚠️ **Your Mac and the server use the same Supabase database today.** Anything you do locally
> (create data, run migrations) happens to the real data too. A separate "dev" Supabase project is
> recommended before real customers arrive (section 9).

---

## 2. Daily work on your Mac 💻

### 2.1 Start your local app

1. Open **Docker Desktop** (Applications → Docker). Wait until the whale icon in the menu bar stops moving.
2. In the project folder:

```bash
cd ~/Projects/chatbot-platform
make up          # starts API + worker + Redis in Docker
make ps          # check: api, redis, worker -> "healthy"
```

3. Bot Studio, in a **second** terminal tab:

```bash
make studio      # leave this running; open http://localhost:5173
```

| Open | You should see |
|---|---|
| http://localhost:8000/health | `{"status":"ok"}` |
| http://localhost:8000/docs | List of API endpoints (only shown locally) |
| http://localhost:5173 | Saathi Studio ("missing bearer token" is expected until the login screen exists) |

### 2.2 Watch what's happening

```bash
make logs        # live API + worker output (Ctrl+C stops watching, app keeps running)
```

### 2.3 Stop everything

```bash
make down        # stops API, worker, Redis
```
In the Bot Studio tab: press **Ctrl+C**. You can also quit Docker Desktop to save battery.

### 2.4 Before you push code: run the checks

```bash
make lint && make typecheck && make test          # backend
cd dashboard && npm run typecheck && npm test && npm run build && cd ..   # Bot Studio
```
✅ Everything ends without red `FAILED` / `error` lines. The backend shows something like
`235 passed, 25 skipped`.

### 2.5 Getting your changes onto GitHub

```bash
git switch main && git pull            # start from the latest code
git switch -c my-change-name           # a new branch for your change
# ... make your changes ...
git add -A && git commit -m "describe the change"
git push -u origin my-change-name
```
Then on GitHub: open the pull request → wait for **all checks green ✓** → **Merge**.
Only merged, green code should go to the server.

---

## 3. Releasing to the server 🖥️ (whenever `main` has something new)

### 3.1 Log in

💻 From your Mac:
```bash
ssh root@SERVER_IP
```
(Or use **Terminal** in Hostinger hPanel → VPS.) ✅ The prompt shows `root@srv2128403`.

### 3.2 The 3 release commands

```bash
cd ~/Projects/chatbot-platform
docker compose --env-file .env -f infra/docker-compose.prod.yml down
git pull
docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --build
```

| Command | What it does |
|---|---|
| `down` | Stops Saathi (n8n and Traefik keep running). **Optional**: skipping it shortens downtime from minutes to seconds |
| `git pull` | Downloads the latest code from GitHub `main` |
| `up -d --build` | Builds the new version, **runs the database migration first** (the app only starts if it succeeds), then starts the API, worker, Redis and Bot Studio |

The build takes 1–10 minutes. Wait for the prompt to come back.

> **Tip: shorter commands.** Run this once on the server:
> ```bash
> echo "alias saathi='docker compose --env-file /root/Projects/chatbot-platform/.env -f /root/Projects/chatbot-platform/infra/docker-compose.prod.yml'" >> ~/.bashrc && source ~/.bashrc
> ```
> Then the release is `saathi down` → `git pull` → `saathi up -d --build`, and `saathi ps` /
> `saathi logs -f api` work everywhere below.

### 3.2a Before the first Phase 2 release (once)

The Phase 2 release adds migration **0004** (new nullable columns + the `unanswered_questions`
table; additive, safe while the old version runs) and a worker that processes documents. Before
running the 3 commands the first time:

1. **Supabase → Storage → New bucket**: name `documents` (or the value of
   `SUPABASE_STORAGE_PRIVATE_BUCKET`), **Public: off**. The code never creates buckets.
2. Check `.env` on the server has `GEMINI_API_KEY`, `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
   The worker now **refuses to start** without its storage and embedding settings (it would fail
   every job otherwise). `COHERE_API_KEY` is needed for answers (reranking), not for ingestion.
3. The image is bigger (document parsers + Tesseract OCR with English, Hindi and Bengali), so the
   first build takes a few minutes longer.

After the release: `DC logs --tail 50 worker` should show the worker started without
`ConfigurationError`, and `DC ps` shows `migrate` Exited (0).

### 3.3 Check the release worked

```bash
docker compose --env-file .env -f infra/docker-compose.prod.yml ps
```
✅ `api`, `redis`, `worker`, `studio`: **Up (healthy)** · `migrate`: **Exited (0)** (a one-time job: correct).

```bash
curl -s http://127.0.0.1:8000/health; echo
```
✅ `{"status":"ok"}`

Then in your browser:

| Open | Expect |
|---|---|
| https://api.saathi.sahil-aisolution.cloud/health | `{"status":"ok"}` |
| https://app.saathi.sahil-aisolution.cloud | Saathi Studio |
| https://api.saathi.sahil-aisolution.cloud/docs | `Not found`: correct (docs are off in production) |
| Your n8n address | n8n works as before |

---

## 4. Daily and weekly checks (2 minutes)

| How often | Check | How |
|---|---|---|
| Daily | API is up | Open https://api.saathi.sahil-aisolution.cloud/health → `{"status":"ok"}` |
| Daily | Bot Studio loads | Open https://app.saathi.sahil-aisolution.cloud |
| Daily | n8n works | Open your n8n address |
| Weekly | All containers healthy | 🖥️ `docker compose --env-file .env -f infra/docker-compose.prod.yml ps` |
| Weekly | Disk space | 🖥️ `df -h /`: keep **Use%** under 80% |
| Weekly | Errors in the logs | 🖥️ `docker compose --env-file .env -f infra/docker-compose.prod.yml logs --since 24h api \| grep -iE "error\|exception" \| tail -20` |
| Weekly | GitHub `main` is green | GitHub → repository → latest commit shows ✓ |
| Monthly | Supabase backups | Supabase dashboard → Database → Backups |

**Automatic, no action needed:** HTTPS certificates (Traefik renews them), Ubuntu security
updates, restarts after a server reboot (containers come back by themselves).

Optional but recommended: a free uptime monitor (UptimeRobot or Better Stack) on
`https://api.saathi.sahil-aisolution.cloud/health`, which emails you when it goes down.

---

## 5. Useful server commands 🖥️

Always start with `cd ~/Projects/chatbot-platform`. `DC` below means
`docker compose --env-file .env -f infra/docker-compose.prod.yml` (or `saathi`, if you set up the alias).

| I want to... | Command |
|---|---|
| See status | `DC ps` |
| Watch API logs live | `DC logs -f --tail 100 api` (Ctrl+C to stop watching) |
| See worker logs | `DC logs --tail 100 worker` |
| See why a release failed | `DC logs migrate` or `DC logs studio` |
| Restart the app (no rebuild) | `DC restart api worker` |
| Restart Traefik (fixes "404" on all sites) | `docker restart traefik-traefik-1` |
| See everything Docker runs (incl. n8n) | `docker ps` |
| Free disk space (old images) | `docker image prune -f` |

---

## 6. Changing a setting on the server

1. 🖥️ Edit the settings file:
   ```bash
   cd ~/Projects/chatbot-platform
   nano .env
   ```
   Move with the arrow keys, change the value, save with **Ctrl+O** then **Enter**, exit with **Ctrl+X**.
2. Apply it (no rebuild needed for settings):
   ```bash
   docker compose --env-file .env -f infra/docker-compose.prod.yml up -d
   ```

Settings that must stay like this in production:
```bash
ENV=production
SAATHI_BASE_DOMAIN=saathi.sahil-aisolution.cloud
```
Keep a copy of the production `.env` in your password manager. It's the only thing on the server
you can't get back from GitHub.

---

## 7. Rolling back a bad release

1. 🖥️ Find the last good version:
   ```bash
   cd ~/Projects/chatbot-platform
   git log --oneline -10
   ```
2. Switch to it and rebuild (replace `abc1234` with the commit id you want):
   ```bash
   git checkout abc1234
   docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --build
   ```
3. Once a fix is merged on GitHub, go back to normal:
   ```bash
   git switch main
   git pull
   docker compose --env-file .env -f infra/docker-compose.prod.yml up -d --build
   ```

**Never** run `alembic downgrade` on the server. Rolling back means running older code, not
undoing the database.

---

## 8. Troubleshooting

| You see | Why | Fix |
|---|---|---|
| `saathi: command not found` | The alias isn't set up for this user | Use the full `docker compose ...` command, or set up the alias (section 3.2 tip) |
| `cd: ... chatbot-platform: No such file or directory` | Wrong folder or wrong user | Use `cd ~/Projects/chatbot-platform` as root |
| `required variable SAATHI_BASE_DOMAIN is missing` | The line is missing in `.env` | Add `SAATHI_BASE_DOMAIN=saathi.sahil-aisolution.cloud` (section 6) |
| `service "migrate" didn't complete successfully` | Database migration failed, so the app was **not** started (on purpose) | `DC logs migrate`; usually `MIGRATION_DATABASE_URL` in `.env` is wrong. Fix it, then `up -d --build` again |
| `api` or `studio` is `unhealthy` | The app can't start properly | `DC logs --tail 80 api`: usually a wrong `.env` value. Fix it, then `up -d` |
| `404 page not found` on **every** site, n8n too | Traefik lost its connection to Docker (after a Docker update) | `docker logs --tail 5 traefik-traefik-1` shows `Cannot connect to the Docker daemon` → `docker restart traefik-traefik-1` |
| `404 page not found` only on Saathi | Traefik doesn't know the address | Check `SAATHI_BASE_DOMAIN` matches your DNS exactly, then `up -d` |
| Browser says **Not Secure** but the site works | The browser remembers "Proceed anyway" from the first minute (before the real certificate) | Click **Not Secure** → **Turn on warnings**, or quit the browser (Cmd+Q) and reopen. Check in a private window |
| Certificate warning right after the first release | Traefik is still fetching the certificate | Wait 1–2 minutes and refresh |
| `git pull` complains about local changes | Files were edited on the server | Never edit code on the server: `git restore .`, then `git pull` (`.env` is untouched) |
| 💻 `Cannot connect to the Docker daemon` on your Mac | Docker Desktop isn't running | Open Docker Desktop, wait for the whale icon, try again |
| 💻 `make up` fails on port 6379 or 8000 | Something else uses the port | Stop the other app, or `brew services stop redis` if you installed Redis with Homebrew |
| `worker` restarting, logs show `ConfigurationError` | A storage or embedding setting is missing (Phase 2 worker fails fast) | Add the named variable to `.env` (section 3.2a), then `up -d` |
| A source stays `queued` for minutes | Its job was lost (Redis was down when it was queued) or the worker is down | Check `DC ps` / `DC logs worker`; then press **Re-sync** on the source (`POST …/sources/{id}/resync` re-sends the job) |
| A source is `failed` with "The AI service refused the request" | The vendor refused for good: wrong key, or unpaid billing (Gemini answers 403 "billing account has an outstanding balance") | Fix the account or key in `.env`, then press **Re-sync** on the source |
| A source is `failed` with "We could not read this file" | The file is broken, encrypted or not what its name says | Open it on your Mac; re-save as a normal PDF/DOCX and upload again |
| GitHub check **dashboard** red with "EXPIRED" | The reviewed npm-audit exception reached its date | Re-check whether `picomatch` has a fix (merge the Dependabot PR), then update or remove `dashboard/audit-exceptions.json` |

When stuck: copy the **exact** error text and the command you ran, and ask for help.

---

## 9. Rules that keep you safe

- ❌ **Never** `docker compose ... down -v`: the `-v` deletes Redis' data (the job queue).
- ❌ **Never** stop, remove or edit **Traefik** or **n8n** for Saathi. They're shared.
- ❌ **Never** edit code on the server. Change it on your Mac → GitHub → `git pull`.
- ❌ **Never** commit `.env` or paste keys and passwords into chats or tickets. If one leaks, rotate it in that provider's dashboard.
- ❌ **Never** run `alembic downgrade` in production.
- ✅ Only release code that's **merged and green** on GitHub.
- ✅ Keep a copy of the production `.env` in a password manager.

## 10. Open to-dos (as of 2026-11-22)

| To-do | Why |
|---|---|
| Rotate the Supabase secret key (if not done) | It was exposed in a chat earlier |
| Separate Supabase project for local development | Today your Mac and the server share the real database |
| Move Supabase to Mumbai (`ap-south-1`) | The server is in Mumbai; every database call goes to Singapore and back |
| Close n8n's direct port (`32772`, plain HTTP) | It bypasses Traefik and HTTPS. Ask for the exact safe change |
| npm-audit exception expires **2026-12-17** | `picomatch` advisory: merge the fix when Dependabot offers it |
| Bot Studio login screen (P5.9) | Needed before bots can be created from the dashboard |
| Add `COHERE_API_KEY` locally and on the server | Reranking (and therefore confident answers and the real golden eval) needs it |
| Review `evals/golden/golden_v1.jsonl` | Drafted from the demo documents; tuning results count only after your review |
| One copy of the project on the server | `/home/deploy/chatbot-platform` from the setup script is unused; remove it with `rm -rf /home/deploy/chatbot-platform` |

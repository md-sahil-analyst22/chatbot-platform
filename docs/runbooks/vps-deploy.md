# Runbook: deploy to a Hostinger VPS (ADR-0008)

For a Hostinger **n8n VPS template** server (Ubuntu 24.04 with **Traefik** + **n8n** already running).
Saathi plugs into that existing Traefik, which also serves n8n and gives every site free HTTPS.
Nothing in this guide stops or changes n8n or Traefik.

Takes about **45 minutes** the first time. After that, a release is **three commands** on the server,
run by you whenever you choose (nothing deploys automatically).

**What you'll end up with**
- `https://api.saathi.yourdomain.com`: the API
- `https://app.saathi.yourdomain.com`: Bot Studio
- n8n keeps working exactly as before
- A hardened server: firewall, SSH keys only, automatic security updates

**Your base address.** This guide uses **`saathi.yourdomain.com`** as the example. Replace it
everywhere with **your real one** (e.g. `saathi.mydomain.in`), and **`SERVER_IP`** with your VPS's
IP address (hPanel → VPS → Overview). The scripts refuse the example address on purpose.

**Where to type:** 💻 = your Mac's Terminal · 🖥️ = on the server (after logging in).

**How it fits together**

```
Browser ──HTTPS──> Traefik (already on the server) ─┬─ n8n address      ──> n8n (unchanged)
                                                    ├─ api.saathi.<...> ──> Saathi API
                                                    └─ app.saathi.<...> ──> Bot Studio
```

---

## Step 1: 💻 Check your SSH key

```bash
cat ~/.ssh/id_ed25519.pub
```
- ✅ One line starting `ssh-ed25519`: you have a key.
- ❌ `No such file`: run `ssh-keygen -t ed25519` (press Enter for every question) and `cat` again.

If you didn't add this key in Hostinger when buying the VPS, run `ssh-copy-id root@SERVER_IP` and
type the root password once.

## Step 2: Hostinger DNS: point your addresses at the server

hPanel → **Domains** → your domain → **DNS records**, add **two A records**:

| Type | Name | Points to | TTL |
|---|---|---|---|
| A | `api.saathi` | `SERVER_IP` | 300 |
| A | `app.saathi` | `SERVER_IP` | 300 |

The **Name** is the part before your domain. Your n8n and other records stay as they are.
After 5–30 minutes, check on 💻:

```bash
dig +short api.saathi.yourdomain.com
dig +short app.saathi.yourdomain.com
```
✅ Both print `SERVER_IP`.

## Step 3: 💻 Log in to the server as root

```bash
ssh root@SERVER_IP
```
Type `yes` if asked to continue connecting. ✅ The prompt shows `root@srv...`.

## Step 4: 🖥️ Run the setup script (about 5–10 minutes)

```bash
cd ~
curl -fsSL https://raw.githubusercontent.com/md-sahil-analyst22/chatbot-platform/main/scripts/vps/setup.sh -o setup.sh
sudo bash setup.sh saathi.yourdomain.com
```

It runs 10 steps and ends with `Done.`. It's safe to run again at any time. If you ran an older
version that tried to install nginx, this version removes that leftover automatically.

| If you see | Meaning |
|---|---|
| `Traefik '...' is ready` | ✅ Saathi will use the existing Traefik |
| `password and root logins disabled` | ✅ From now on log in as `ssh deploy@SERVER_IP` |
| `... points to 'nothing', not this server` | DNS isn't ready. Fine for now; HTTPS starts working once it is (step 2) |
| `is the guide's example` | Use your **real** domain instead of `yourdomain.com` |
| `no running Traefik container found` | This server isn't the n8n template. **Stop** and ask your developer |

Then type `exit` to leave the server.

## Step 5: Supabase: rotate the secret key first

The old Supabase secret key was exposed in a chat, so replace it. Supabase → **Project Settings
→ API Keys** → create a new **secret** key → **delete the old one**. Put the new key on the
`SUPABASE_SERVICE_ROLE_KEY=` line of your local `.env` and save.

## Step 6: Put your settings on the server

💻 In the project folder on your Mac:

```bash
scp .env deploy@SERVER_IP:/home/deploy/chatbot-platform/.env
ssh deploy@SERVER_IP
```

🖥️ Now on the server as `deploy` (the prompt shows `deploy@srv...`):

```bash
chmod 600 ~/chatbot-platform/.env
nano ~/chatbot-platform/.env
```

Make sure these **two lines** look like this (change them, or add them at the end):

```bash
ENV=production
SAATHI_BASE_DOMAIN=saathi.yourdomain.com
```

Save with **Ctrl+O**, then **Enter**, and exit with **Ctrl+X**. That's all: the API and Studio
addresses, CORS and HTTPS are derived from `SAATHI_BASE_DOMAIN`.

`ENV=production` means the API **refuses to start** without the `AUTH_*` lines (already in your
`.env` if it works locally) and switches the `/docs` page off.

## Step 7: 🖥️ Release: your 3 commands

```bash
cd ~/chatbot-platform
saathi down              # 1. stop the running app (optional - see below)
git pull                 # 2. get the latest code from GitHub
saathi up -d --build     # 3. build and start the new version
```

If `saathi` says `command not found`, type `exit`, log in again as `deploy`, and retry.
`saathi` is a short name for `docker compose --env-file .env -f infra/docker-compose.prod.yml`.

**What step 3 does by itself:**
1. builds the backend and Bot Studio images;
2. runs the **database migration**. If it fails, the API and worker are **not** started;
3. starts Redis, the API, the worker and Bot Studio;
4. Traefik notices the new containers and gets HTTPS certificates for both addresses
   (the first time can take up to a minute).

The first run takes 5–10 minutes; later releases are faster.

**About `saathi down`:** the site is offline from `down` until step 3 finishes (the whole build).
Running only steps 2 and 3 takes it down for a few seconds instead. Both are safe. **Never** use
`saathi down -v`: that deletes Redis' data. Only pull commits that show a **green ✓** on GitHub.

**Check it:**

```bash
saathi ps
```
✅ `api`, `redis`, `worker`, `studio`: **Up (healthy)** · `migrate`: **Exited (0)** (a one-time job).

Then in your browser:

| Open | Expect |
|---|---|
| `https://api.saathi.yourdomain.com/health` | `{"status":"ok"}` with a 🔒 padlock |
| `https://app.saathi.yourdomain.com` | Saathi Studio ("missing bearer token" is expected until the Studio login exists, P5.9) |
| `https://api.saathi.yourdomain.com/docs` | `Not found`: correct, docs are off in production |
| `http://api.saathi.yourdomain.com/health` | Switches to `https://` automatically |
| Your n8n address | n8n works as before |

---

## Everyday operations

On the server: `ssh deploy@SERVER_IP`, then `cd ~/chatbot-platform`.

| I want to... | Command |
|---|---|
| Release a new version | `saathi down` → `git pull` → `saathi up -d --build` |
| See if everything runs | `saathi ps` |
| Watch the API logs | `saathi logs -f --tail 100 api` (Ctrl+C to stop) |
| Why did a release fail? | `saathi logs migrate` or `saathi logs studio` |
| Restart the app | `saathi restart api worker` |
| Roll back | `git log --oneline -10` → `git checkout <good-commit>` → `saathi up -d --build`. Back to normal: `git switch main` → `git pull` → `saathi up -d --build` |
| Check disk space | `df -h /` (keep it under 80%) |

**Backups:** the database is in Supabase (check its backup policy). The server holds only code and
`.env`, so keep a copy of the production `.env` in your password manager. Hostinger snapshots
(hPanel) are a useful extra. **Never** run `alembic downgrade` in production (R25).

## Troubleshooting

| Problem | Fix |
|---|---|
| `Permission denied (publickey)` | Log in as `deploy`: `ssh deploy@SERVER_IP`, from the Mac that has your key |
| `required variable SAATHI_BASE_DOMAIN is missing` | Add `SAATHI_BASE_DOMAIN=...` to `.env` (step 6) |
| `service "migrate" didn't complete successfully` | The migration failed and the API was **not** started. Run `saathi logs migrate`; usually `MIGRATION_DATABASE_URL` in `.env` is wrong |
| Browser shows "not secure" / certificate warning | DNS isn't pointing at the server yet, or it changed in the last minutes. Check step 2; Traefik retries automatically |
| `404 page not found` (plain text) | Traefik doesn't know the address. Check `SAATHI_BASE_DOMAIN` in `.env` matches your DNS names exactly, then `saathi up -d` |
| `api` is `unhealthy` | `saathi logs --tail 80 api`: usually a wrong `.env` value. Fix it, then `saathi up -d` |
| `git pull` complains about local changes | Never edit code on the server: `git restore .`, then pull again (`.env` is untouched) |
| n8n stopped working | Saathi doesn't touch it, but check: `docker ps` should show the n8n and traefik containers **Up** |

## Recommended soon

- **Close n8n's direct port.** The Hostinger template also publishes n8n on a high port
  (`docker ps` shows `0.0.0.0:327xx->5678`), reachable over plain HTTP, bypassing Traefik and
  the firewall (Docker opens it). n8n works fine without it through Traefik. Ask your developer
  for the exact change before editing Hostinger's n8n files.
- Move the Supabase project to **Mumbai** (`ap-south-1`), next to the server.
- Add an uptime monitor (UptimeRobot / Better Stack) on `https://api.saathi.yourdomain.com/health`.

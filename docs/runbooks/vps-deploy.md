# Runbook: deploy to a Hostinger VPS (ADR-0008)

Takes about **1 hour** the first time. After that, releasing a new version is **three commands** on
the server, run by you whenever you choose (nothing deploys automatically).

**What you'll end up with**
- `https://api.saathi.yourdomain.com`: the API (HTTPS, behind nginx)
- `https://app.saathi.yourdomain.com`: Bot Studio
- A hardened server: firewall, SSH keys only, automatic security updates
- Manual releases: `saathi down` → `git pull` → `saathi up -d --build`

**Words you'll see**

| Word | Meaning |
|---|---|
| VPS | Your own small Linux server in a data centre |
| SSH | A secure way to type commands on that server from your Mac's terminal |
| SSH key | A pair of files that replaces a password: the *private* key stays on your Mac, the *public* key goes on the server |
| DNS | The internet's phone book: it maps `api.saathi.yourdomain.com` to your server's IP address |
| nginx | The front door on the server: handles HTTPS and forwards requests to the app |

**Your project's base address.** This guide uses **`saathi.yourdomain.com`**: a sub-domain just for
this project, so the same domain can host other projects too. Replace it everywhere with your own
(for example `saathi.mydomain.in`), and replace **`SERVER_IP`** with your VPS's IP address. The
scripts put `api.` and `app.` in front of whatever base address you give them.

---

## Step 1: Create an SSH key on your Mac (5 min)

In the Mac Terminal:

```bash
ls ~/.ssh/id_ed25519.pub 2>/dev/null || ssh-keygen -t ed25519 -C "my-mac"
```

If it asks questions, press **Enter** to accept the defaults. Setting a passphrase is recommended.
Then show your **public** key:

```bash
cat ~/.ssh/id_ed25519.pub
```

✅ One line starting with `ssh-ed25519 AAAA...`. Copy it; you'll paste it into Hostinger.
❌ Never share `~/.ssh/id_ed25519` (the file **without** `.pub`). That one is private.

## Step 2: Buy the VPS on Hostinger (10 min)

In Hostinger's hPanel, buy a VPS. Menu names can change slightly; choose:

| Setting | Choose |
|---|---|
| Plan | **KVM 2** (2 vCPU / 8 GB) recommended. KVM 1 (4 GB) works for testing |
| Location | **India** (Mumbai) |
| Operating system | **Ubuntu 24.04** as a *plain OS* (no control panel, no app template) |
| SSH key | Paste the public key from step 1 |
| Root password | Set a strong one and save it in a password manager (emergency use only) |

When it's ready, copy the server's **IPv4 address** from hPanel. That's your `SERVER_IP`.

## Step 3: Point your domain at the server (5 min, then wait)

In hPanel → **Domains** → your domain → **DNS / Nameservers** → DNS records, add **two A records**:

| Type | Name | Points to | TTL |
|---|---|---|---|
| A | `api.saathi` | `SERVER_IP` | 300 (or default) |
| A | `app.saathi` | `SERVER_IP` | 300 (or default) |

The **Name** is everything before your domain: for `api.saathi.yourdomain.com` it's `api.saathi`.
Some DNS panels want the full name instead, which is also fine. Your other projects' records are
unaffected. If your domain is at another registrar, add the same two records there.
DNS takes **5–30 minutes** (sometimes longer). Check from your Mac:

```bash
dig +short api.saathi.yourdomain.com
dig +short app.saathi.yourdomain.com
```

✅ Both print `SERVER_IP`. You can keep going while you wait; step 5 tells you if DNS isn't ready.

## Step 4: First login to the server (2 min)

```bash
ssh root@SERVER_IP
```

The first time, it asks `Are you sure you want to continue connecting?`: type `yes`.
✅ The prompt changes to something like `root@srv123:~#`. You're now typing **on the server**.

## Step 5: Run the setup script (10 min)

The pull request with these scripts must be **merged into `main`** first, so the server can download
them. Still logged in as root:

```bash
curl -fsSL https://raw.githubusercontent.com/md-sahil-analyst22/chatbot-platform/main/scripts/vps/setup.sh -o setup.sh
less setup.sh                                   # optional: read what it will do (press q to exit)
sudo bash setup.sh saathi.yourdomain.com you@example.com
```

Give the **base address** (`saathi.yourdomain.com`), not `api.` or `app.`: the script adds those.

The email gets Let's Encrypt notices if a certificate ever fails to renew.

It runs 10 steps (updates, firewall, Docker, nginx, deploy user, HTTPS...) and ends with `Done.`
It also creates the short `saathi` command used in step 7.

| What you see | Meaning |
|---|---|
| `password and root logins disabled` | ✅ From now on log in with `ssh deploy@SERVER_IP` (root login is off) |
| `Skipped HTTPS` | DNS isn't ready yet. Wait, then run `sudo bash setup.sh saathi.yourdomain.com you@example.com` again: it's safe to repeat |
| `no SSH key found for deploy` | Your SSH key wasn't added in step 2. Add it to `/home/deploy/.ssh/authorized_keys` and re-run |

Type `exit` to leave the server.

## Step 6: Put your settings (.env) on the server (10 min)

The server needs the same secrets as your local `.env`, with **three lines changed**.

**First, rotate the Supabase secret key** that was pasted in chat earlier: Supabase → Project
Settings → API Keys → create a new secret key, delete the old one, and update your local `.env`.

Copy your local `.env` to the server. On your **Mac**, from the project folder:

```bash
scp .env deploy@SERVER_IP:/home/deploy/chatbot-platform/.env
ssh deploy@SERVER_IP
chmod 600 ~/chatbot-platform/.env
nano ~/chatbot-platform/.env
```

In `nano`, change these lines (move with the arrow keys, save with **Ctrl+O, Enter**, exit with **Ctrl+X**):

```bash
ENV=production
CORS_ALLOWED_ORIGINS='["https://app.saathi.yourdomain.com"]'
STUDIO_API_BASE_URL=https://api.saathi.yourdomain.com
```

Check that these are already set from your local `.env` (they are, if local works):
`DATABASE_URL`, `MIGRATION_DATABASE_URL`, `AUTH_JWKS_URL`, `AUTH_ISSUER`, `AUTH_AUDIENCE`,
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CREDENTIALS_ENCRYPTION_KEYS`, `GEMINI_*`, `SARVAM_*`.

`ENV=production` means the API **refuses to start** if the `AUTH_*` lines are missing (on purpose),
and the `/docs` page is switched off.

## Step 7: Release by hand: your 3 commands (5–10 min the first time)

Log in as `deploy` and go to the project:

```bash
ssh deploy@SERVER_IP
cd ~/chatbot-platform
```

Then, **every time you want to release a new version**:

```bash
saathi down              # 1. stop the running app (optional - see below)
git pull                 # 2. get the latest code from GitHub (main)
saathi up -d --build     # 3. build and start the new version
```

`saathi` is a short name for `docker compose --env-file .env -f infra/docker-compose.prod.yml`
(created by `setup.sh`). If it says `command not found`, log out and back in once.

**What step 3 does by itself, in this order:**
1. builds the new backend and Bot Studio images;
2. runs the **database migration**. If it fails, the API and worker are **not** started, so new code
   never runs against an old database. You'll see `service "migrate" didn't complete successfully`;
3. starts Redis, the API and the worker;
4. rebuilds Bot Studio and publishes it to the folder nginx serves.

The first time takes several minutes (downloads and builds); later releases are faster.

**About step 1 (`down`):** the site is offline from `down` until step 3 finishes, which is the
whole build (a few minutes). Skipping `down` and running only steps 2 and 3 builds first and then
swaps the containers, so users see only a few seconds of interruption. Both are safe; `down` never
deletes data. **Never add `-v`** (`saathi down -v`): that deletes Redis' data (the job queue).

**Check that it worked:**

```bash
saathi ps
```

✅ `api`, `redis`, `worker` show **Up (healthy)**; `migrate` and `studio` show **Exited (0)**. That's
correct: they're one-shot jobs that finish.

Then in **your Mac's browser**:

| Open | Expect |
|---|---|
| `https://api.saathi.yourdomain.com/health` | `{"status":"ok"}` and a padlock icon |
| `https://app.saathi.yourdomain.com` | Saathi Studio ("missing bearer token" is expected until the Studio login exists, P5.9) |
| `https://api.saathi.yourdomain.com/docs` | `Not found`: correct, docs are off in production |
| `http://api.saathi.yourdomain.com/health` | Redirects to `https://` |

**Release only from green code:** pull after the commit shows a green ✓ (CI passed) on GitHub.

---

## Everyday operations

All on the server: `ssh deploy@SERVER_IP`, then `cd ~/chatbot-platform`.

| I want to... | Command |
|---|---|
| Release a new version | `saathi down` → `git pull` → `saathi up -d --build` (step 7) |
| See if everything runs | `saathi ps` (api, redis, worker **healthy**) |
| Watch the API logs | `saathi logs -f --tail 100 api` (Ctrl+C to stop) |
| Why did a release fail? | `saathi logs migrate` or `saathi logs studio` |
| Restart the app | `saathi restart api worker` |
| Roll back to an older version | `git log --oneline -10` (find the last good commit) → `git checkout <commit>` → `saathi up -d --build`. To return to normal: `git switch main` → `git pull` → `saathi up -d --build` |
| Check HTTPS auto-renewal | `sudo certbot renew --dry-run` |
| Check disk space | `df -h /` (keep it under 80%) |

**Backups:** the database lives in Supabase (check your plan's backup policy in the dashboard).
The server holds no customer data, only the code and `.env`, so keep a copy of the production `.env`
in your password manager. Hostinger snapshots (hPanel) are a useful extra.

**Never** run `alembic downgrade` in production: rolling back means deploying older code (R25).

## Troubleshooting

| Problem | Fix |
|---|---|
| `Permission denied (publickey)` | You're using the wrong user or key. Use `ssh deploy@SERVER_IP` from the Mac that made the key |
| Browser says "not secure" | HTTPS isn't set up yet: check DNS (step 3), then re-run `setup.sh` |
| `502 Bad Gateway` | The app isn't running: check `ps` and the logs (table above) |
| `git pull` says `not possible because you have unmerged files` or `local changes` | Never edit code on the server. Run `git status`, then `git restore .` to throw away server-side edits (`.env` is untouched: git ignores it) |
| `required variable STUDIO_API_BASE_URL is missing` | Add `STUDIO_API_BASE_URL=https://api.saathi.yourdomain.com` to `.env` (step 6) |
| `service "migrate" didn't complete successfully` | The database migration failed and the API was **not** started. Read `saathi logs migrate`; usually `MIGRATION_DATABASE_URL` in `.env` is wrong. Fix it and run `saathi up -d --build` again |
| `api` is `unhealthy` | `saathi logs --tail 80 api`: usually a wrong value in `.env`. Fix it and run `saathi up -d` again, or roll back |
| Bot Studio shows network errors | `STUDIO_API_BASE_URL` or `CORS_ALLOWED_ORIGINS` don't match your domains exactly (https, no trailing `/`) |

## Sharing one VPS with other projects

This setup assumes the VPS runs **only Saathi**. Before adding another project to the same server, check:
- **Port 8000** is used by Saathi's API (on `127.0.0.1`), so give the other app a different port.
- The Docker network `172.30.0.0/24` belongs to Saathi; use another subnet for other Compose projects.
- `setup.sh` removes nginx's *default* site. Add other projects as their **own** files in
  `/etc/nginx/sites-available/` (never edit `saathi.conf`, which `setup.sh` overwrites).
- Each project gets its own Let's Encrypt certificate: `sudo certbot --nginx -d other.yourdomain.com`.

Projects on **other** servers need nothing special: just their own DNS records.

## Recommended soon
- Move the Supabase project to **Mumbai** (`ap-south-1`), next to the server. Today every database
  round trip goes to Singapore and back.
- Add an uptime monitor (UptimeRobot / Better Stack) on `https://api.saathi.yourdomain.com/health`.

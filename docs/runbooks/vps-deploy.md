# Runbook: deploy to a Hostinger VPS (ADR-0008)

Takes about **1 hour** the first time. After that, every merge to `main` deploys itself.

**What you'll end up with**
- `https://api.yourdomain.com`: the API (HTTPS, behind nginx)
- `https://app.yourdomain.com`: Bot Studio
- A hardened server: firewall, SSH keys only, automatic security updates
- Automatic deploys from GitHub after CI passes

**Words you'll see**

| Word | Meaning |
|---|---|
| VPS | Your own small Linux server in a data centre |
| SSH | A secure way to type commands on that server from your Mac's terminal |
| SSH key | A pair of files that replaces a password: the *private* key stays on your Mac, the *public* key goes on the server |
| DNS | The internet's phone book: it maps `api.yourdomain.com` to your server's IP address |
| nginx | The front door on the server: handles HTTPS and forwards requests to the app |

Throughout this guide, replace **`yourdomain.com`** with your real domain and **`SERVER_IP`** with
your VPS's IP address.

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
| A | `api` | `SERVER_IP` | 300 (or default) |
| A | `app` | `SERVER_IP` | 300 (or default) |

If your domain is at another registrar, add the same two records there.
DNS takes **5–30 minutes** (sometimes longer). Check from your Mac:

```bash
dig +short api.yourdomain.com
dig +short app.yourdomain.com
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
sudo bash setup.sh yourdomain.com you@example.com
```

The email gets Let's Encrypt notices if a certificate ever fails to renew.

It runs 11 steps (updates, firewall, Docker, nginx, deploy user, HTTPS...). **At the end it prints
three values: copy them somewhere safe for step 8:**
- a block starting `-----BEGIN OPENSSH PRIVATE KEY-----` (**shown only once**)
- `GitHub secret VPS_HOST: ...`
- `GitHub secret VPS_KNOWN_HOSTS: ...`

| What you see | Meaning |
|---|---|
| `password and root logins disabled` | ✅ From now on log in with `ssh deploy@SERVER_IP` (root login is off) |
| `Skipped HTTPS` | DNS isn't ready yet. Wait, then run `sudo bash setup.sh yourdomain.com you@example.com` again: it's safe to repeat |
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
CORS_ALLOWED_ORIGINS='["https://app.yourdomain.com"]'
STUDIO_API_BASE_URL=https://api.yourdomain.com
```

Check that these are already set from your local `.env` (they are, if local works):
`DATABASE_URL`, `MIGRATION_DATABASE_URL`, `AUTH_JWKS_URL`, `AUTH_ISSUER`, `AUTH_AUDIENCE`,
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `CREDENTIALS_ENCRYPTION_KEYS`, `GEMINI_*`, `SARVAM_*`.

`ENV=production` means the API **refuses to start** if the `AUTH_*` lines are missing (on purpose),
and the `/docs` page is switched off.

## Step 7: First deploy, by hand (5–10 min)

Still on the server as `deploy`:

```bash
cd ~/chatbot-platform
./scripts/vps/deploy.sh main
```

✅ It ends with `[deploy ...] done: <commit> is live`. The first run is slower (it downloads and builds).

Check it from **your Mac's browser**:

| Open | Expect |
|---|---|
| `https://api.yourdomain.com/health` | `{"status":"ok"}` and a padlock icon |
| `https://app.yourdomain.com` | Saathi Studio ("missing bearer token" is expected until the Studio login exists, P5.9) |
| `https://api.yourdomain.com/docs` | `Not found`: correct, docs are off in production |
| `http://api.yourdomain.com/health` | Redirects to `https://` |

## Step 8: Turn on automatic deploys (5 min)

On GitHub: your repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add three secrets, with the values printed in step 5:

| Name | Value |
|---|---|
| `VPS_HOST` | the IP address |
| `VPS_SSH_KEY` | the whole private key block, including the `-----BEGIN` and `-----END` lines |
| `VPS_KNOWN_HOSTS` | the whole line (`SERVER_IP ssh-ed25519 AAAA...`) |

Then delete your temporary copy of the private key.
This key can **only** run the deploy script on the server: it can't open a shell.

**Test it:** GitHub → **Actions → Deploy → Run workflow** (leave the commit empty) → **Run**.
✅ A green check. From now on, every merge to `main` deploys automatically once CI is green.

Optional: GitHub → Settings → **Environments → production** → *Required reviewers* (add yourself)
to approve each deploy with one click.

---

## Everyday operations

All on the server: `ssh deploy@SERVER_IP`, then `cd ~/chatbot-platform`.

| I want to... | Command |
|---|---|
| See if everything runs | `docker compose --env-file .env -f infra/docker-compose.prod.yml ps` (all **healthy**) |
| Watch the API logs | `docker compose --env-file .env -f infra/docker-compose.prod.yml logs -f --tail 100 api` (Ctrl+C to stop) |
| Restart the app | `docker compose --env-file .env -f infra/docker-compose.prod.yml restart api worker` |
| Roll back to an older version | GitHub → Actions → Deploy → Run workflow → paste the older commit SHA. Or on the server: `./scripts/vps/deploy.sh <sha>` |
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
| Deploy says `.env must be private` | `chmod 600 ~/chatbot-platform/.env` |
| Deploy says `API not healthy` | The logs are printed above the error. Usually a wrong value in `.env`. Fix it and deploy again. The previous version was already replaced, so deploy the last good commit if needed |
| Bot Studio shows network errors | `STUDIO_API_BASE_URL` or `CORS_ALLOWED_ORIGINS` don't match your domains exactly (https, no trailing `/`) |
| GitHub Deploy says "skipped" | The three secrets from step 8 aren't set |

## Recommended soon
- Move the Supabase project to **Mumbai** (`ap-south-1`), next to the server. Today every database
  round trip goes to Singapore and back.
- Add an uptime monitor (UptimeRobot / Better Stack) on `https://api.yourdomain.com/health`.

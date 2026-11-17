# scripts/

| Script | When | Command |
|---|---|---|
| `check_keys.py` | Phase 0 exit check: one cheap call per provider | `make check-keys` |
| `check_keys.py --send-whatsapp` | Sends the `hello_world` template to `WHATSAPP_TEST_RECIPIENT` | `make check-keys ARGS=--send-whatsapp` |
| `vps/setup.sh` | Once, on a fresh Ubuntu 24.04 VPS, as root | `sudo bash setup.sh saathi.yourdomain.com` (see `docs/runbooks/vps-deploy.md`) |

Rules: scripts never print secret values; they read `.env` from the repo root.

Releases need no script: on the server run `saathi down` → `git pull` → `saathi up -d --build` (docs/runbooks/vps-deploy.md, step 7).

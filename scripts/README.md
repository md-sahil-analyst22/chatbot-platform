# scripts/

| Script | When | Command |
|---|---|---|
| `check_keys.py` | Phase 0 exit check: one cheap call per provider | `make check-keys` |
| `check_keys.py --send-whatsapp` | Sends the `hello_world` template to `WHATSAPP_TEST_RECIPIENT` | `make check-keys ARGS=--send-whatsapp` |
| `vps/setup.sh` | Once, on a fresh Ubuntu 24.04 VPS, as root | `sudo bash setup.sh yourdomain.com you@example.com` (see `docs/runbooks/vps-deploy.md`) |
| `vps/deploy.sh` | Every release (CI calls it automatically) | on the server: `./scripts/vps/deploy.sh <sha>\|main` |

Rules: scripts never print secret values; they read `.env` from the repo root.

One documented exception: `vps/setup.sh` prints the GitHub Actions deploy key **once**, on the operator's own
terminal, so it can be pasted into the `VPS_SSH_KEY` secret; the server copy is deleted right after. That key is
restricted to running `deploy.sh` (no shell). To rotate it, delete the `gha-deploy` line from
`/home/deploy/.ssh/authorized_keys` and re-run `setup.sh`.

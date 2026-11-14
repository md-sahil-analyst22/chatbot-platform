# scripts/

| Script | When | Command |
|---|---|---|
| `check_keys.py` | Phase 0 exit check: one cheap call per provider | `make check-keys` |
| `check_keys.py --send-whatsapp` | Sends the `hello_world` template to `WHATSAPP_TEST_RECIPIENT` | `make check-keys ARGS=--send-whatsapp` |

Rules: scripts never print secret values; they read `.env` from the repo root.

#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: End-to-end check of the LIVE system after a release: health, login, bots, config, public
#       widget.
# Run: make smoke-live. It signs in as the owner, creates a temporary test bot and deletes it
#      again.
# Security: 🔒 Asks for your email and password in the terminal; never stores or prints them,
#           or any token.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Phase 1 exit check on the LIVE API: real Supabase login, then create / configure / publish.

Proves the last Phase 1 exit criterion (05_PHASEWISE_DEVELOPMENT_PLAN):
  "POST /bots and POST /bots/{id}/config/versions work on the public URL with a valid token"
plus "publishing twice leaves exactly one published version", against the real server.

Usage (from the repo root, on your Mac):
    make smoke-live                         # API at https://api.$SAATHI_BASE_DOMAIN
    make smoke-live ARGS="--base saathi.example.com --keep"

Needs in .env: SUPABASE_URL, SUPABASE_ANON_KEY (the publishable key). Asks for your email and
password in the terminal (never stored or printed). The test bot is deleted at the end unless you
pass --keep. Never prints tokens, passwords or keys. Exit code 1 if any step fails.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = httpx.Timeout(30.0)
failed = False


# Read .env into the environment.
def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


# One setting's value.
def env(name: str) -> str:
    return os.environ.get(name, "").strip()


# Print one ✅/❌ line and return whether it passed.
def step(ok: bool, label: str, detail: str = "") -> bool:
    global failed
    failed |= not ok
    print(f"{'✅' if ok else '❌'} {label}" + (f"  ({detail})" if detail else ""))
    return ok


# Pull the error code out of an API response for a readable message.
def error_of(r: httpx.Response) -> str:
    """The API's own error code/message (never secrets), or the HTTP status."""
    try:
        body = r.json()
    except ValueError:
        return f"HTTP {r.status_code}"
    if not isinstance(body, dict):  # successful list responses aren't errors
        return f"HTTP {r.status_code}"
    err = body.get("error", {})
    return f"HTTP {r.status_code} {err.get('code', '')}: {err.get('message', '')}".strip()


# Show which algorithm signed the token (safe public info - never the token itself).
def token_header(token: str) -> str:
    """Algorithm and key id from the token header (public metadata, not the token)."""
    try:
        head = token.split(".")[0]
        data = json.loads(base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
        return f"alg={data.get('alg')}, kid={'yes' if data.get('kid') else 'missing'}"
    except (ValueError, IndexError):
        return "unreadable"


# Run every check in order; exit code 0 = all passed.
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--base", help="base address, e.g. saathi.example.com (default: SAATHI_BASE_DOMAIN)"
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the test bot instead of deleting it"
    )
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    base = (
        args.base
        or env("SAATHI_BASE_DOMAIN")
        or input("Base address (e.g. saathi.example.com): ").strip()
    )
    api = f"https://api.{base}"
    supabase_url, anon_key = env("SUPABASE_URL").rstrip("/"), env("SUPABASE_ANON_KEY")
    if not supabase_url or not anon_key:
        print("❌ Set SUPABASE_URL and SUPABASE_ANON_KEY (the publishable key) in .env first.")
        return 1

    print(f"Testing {api}\n")
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False) as c:
        r = c.get(f"{api}/health")
        if not step(
            r.status_code == 200,
            "API is up (GET /health)",
            error_of(r) if r.status_code != 200 else "",
        ):
            return 1

        email = input("Your Supabase login email: ").strip()
        password = getpass.getpass("Password (hidden): ")
        r = c.post(
            f"{supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": anon_key},
            json={"email": email, "password": password},
        )
        del password
        token = r.json().get("access_token") if r.status_code == 200 else None
        if not step(
            bool(token),
            "Logged in with Supabase",
            "" if token else f"HTTP {r.status_code}: check email/password",
        ):
            return 1
        print(f"   token type: {token_header(token)}  (the API accepts ES256/RS256 only)")
        auth = {"Authorization": f"Bearer {token}"}

        r = c.get(f"{api}/api/v1/bots", headers=auth)
        if not step(
            r.status_code == 200, "Token accepted, workspace found (GET /api/v1/bots)", error_of(r)
        ):
            if r.status_code == 403:
                print("   -> no workspace for your user yet: run the step-2 SQL.")
            return 1

        r = c.get(f"{api}/api/v1/model-options", headers=auth)
        options = r.json() if r.status_code == 200 else []
        if not step(
            bool(options),
            "A model is available on your plan (GET /api/v1/model-options)",
            error_of(r) if r.status_code != 200 else f"{len(options)} option(s)",
        ):
            print("   -> set GEMINI_MODEL_SMALL in the server's .env, then restart the app.")
            return 1
        model_key = options[0]["key"]

        name = f"Smoke test {time.strftime('%Y-%m-%d %H:%M:%S')}"
        r = c.post(
            f"{api}/api/v1/bots", headers=auth, json={"name": name, "languages": ["en", "bn"]}
        )
        if not step(
            r.status_code == 201,
            "Created a bot (POST /api/v1/bots)",
            error_of(r) if r.status_code != 201 else name,
        ):
            return 1
        bot = r.json()
        base_cfg = f"{api}/api/v1/bots/{bot['id']}/config/versions"
        try:
            for title in ("Smoke v1", "Smoke v2"):
                config = {
                    "branding": {"header_title": title, "greeting": "নমস্কার!"},
                    "generation": {"model_key": model_key},
                }
                r = c.post(base_cfg, headers=auth, json=config)
                if not step(
                    r.status_code == 201,
                    f"Saved draft '{title}' (POST config/versions)",
                    error_of(r) if r.status_code != 201 else f"v{r.json().get('version')}",
                ):
                    return 1
                version = r.json()["version"]
                r = c.post(f"{base_cfg}/{version}/publish", headers=auth)
                ok = r.status_code == 200 and r.json().get("status") == "published"
                if not step(ok, f"Published v{version}", "" if ok else error_of(r)):
                    return 1

            r = c.get(base_cfg, headers=auth)
            live = (
                [v["version"] for v in r.json() if v["status"] == "published"]
                if r.status_code == 200
                else []
            )
            step(
                live == [2],
                "After publishing twice, exactly one version is live",
                f"live versions: {live}",
            )

            r = c.get(f"{api}/public/v1/widgets/{bot['public_key']}/config")
            ok = r.status_code == 200 and r.json().get("header_title") == "Smoke v2"
            step(
                ok,
                "Public widget config shows the published look (no login)",
                "" if ok else error_of(r),
            )
            if ok:
                leaked = {"bot_id", "persona", "model_key", "plan"} & set(r.json())
                step(
                    not leaked,
                    "Public response contains no internal fields",
                    f"unexpected: {sorted(leaked)}" if leaked else "",
                )
        finally:
            if args.keep:
                print(f"\nKept the test bot '{name}' (--keep).")
            else:
                r = c.delete(f"{api}/api/v1/bots/{bot['id']}", headers=auth)
                step(
                    r.status_code == 204,
                    "Deleted the test bot (DELETE /api/v1/bots/{id})",
                    error_of(r) if r.status_code != 204 else "",
                )

    print(
        "\n"
        + ("❌ Some checks failed - see above." if failed else "✅ Phase 1 live checks passed.")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\ncancelled.")
        sys.exit(1)

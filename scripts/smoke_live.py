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

# From __future__ — Python language switches: annotations = lets type hints mention classes
#   defined later.
from __future__ import annotations

# argparse — reads command-line options such as --keep.
import argparse
# base64 — turns bytes into text and back.
import base64
# getpass — asks for a password without showing it on screen.
import getpass
# json — reads and writes JSON text.
import json
# os — talks to the operating system (environment variables, files).
import os
# sys — Python runtime details (output streams, exit codes).
import sys
# time — clocks and timers.
import time
# From pathlib — file and folder paths: Path = a file or folder path.
from pathlib import Path

# httpx — the HTTP client we use to call other web services.
import httpx

# The repository's top folder.
REPO_ROOT = Path(__file__).resolve().parents[1]
# Give each request at most 30 seconds.
TIMEOUT = httpx.Timeout(30.0)
# Becomes True as soon as any check fails.
failed = False


# Read .env into the environment.
def load_dotenv(path: Path) -> None:
    # No .env file...
    if not path.exists():
        # ...then nothing to load.
        return
    # Go through the file line by line:
    for raw in path.read_text(encoding="utf-8").splitlines():
        # trim spaces;
        line = raw.strip()
        # skip blank lines, comments and lines without '='...
        if not line or line.startswith("#") or "=" not in line:
            # ...like this.
            continue
        # Split 'NAME=value' at the first '='.
        key, _, value = line.partition("=")
        # Drop a trailing ' # comment' and surrounding quotes.
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        # Set it, unless it's already set in the real environment.
        os.environ.setdefault(key.strip(), value)


# One setting's value.
def env(name: str) -> str:
    # The variable's value without spaces ('' if not set).
    return os.environ.get(name, "").strip()


# Print one ✅/❌ line and return whether it passed.
def step(ok: bool, label: str, detail: str = "") -> bool:
    # `global` lets this function change the file-level `failed` flag.
    global failed
    # Remember a failure (stays True once set).
    failed |= not ok
    # Print ✅ or ❌, the label, and the detail in brackets if there is one.
    print(f"{'✅' if ok else '❌'} {label}" + (f"  ({detail})" if detail else ""))
    # Return whether it passed, so callers can stop early.
    return ok


# Pull the error code out of an API response for a readable message.
def error_of(r: httpx.Response) -> str:
    """The API's own error code/message (never secrets), or the HTTP status."""
    # Try to read the JSON body...
    try:
        # ...as `body`.
        body = r.json()
    # Not JSON:
    except ValueError:
        # just the status code.
        return f"HTTP {r.status_code}"
    if not isinstance(body, dict):  # successful list responses aren't errors
        # just the status code.
        return f"HTTP {r.status_code}"
    # Our API's error part, if present.
    err = body.get("error", {})
    # e.g. 'HTTP 403 forbidden: requires role >= admin'.
    return f"HTTP {r.status_code} {err.get('code', '')}: {err.get('message', '')}".strip()


# Show which algorithm signed the token (safe public info - never the token itself).
def token_header(token: str) -> str:
    """Algorithm and key id from the token header (public metadata, not the token)."""
    # Try to read the token's first part (its header):
    try:
        # the text before the first '.',
        head = token.split(".")[0]
        # decoded from base64 (adding the padding back) and parsed as JSON.
        data = json.loads(base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
        # Report the algorithm and whether there's a key id.
        return f"alg={data.get('alg')}, kid={'yes' if data.get('kid') else 'missing'}"
    # Not a readable token:
    except (ValueError, IndexError):
        # say so.
        return "unreadable"


# Run every check in order; exit code 0 = all passed.
def main() -> int:
    # Read command-line options; the help text is the first line of this file's description.
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # --base: which domain to test,
    parser.add_argument(
        "--base", help="base address, e.g. saathi.example.com (default: SAATHI_BASE_DOMAIN)"
    )
    # --keep: don't delete the test bot at the end.
    parser.add_argument(
        "--keep", action="store_true", help="keep the test bot instead of deleting it"
    )
    # Parse them.
    args = parser.parse_args()

    # Load the repository's .env file.
    load_dotenv(REPO_ROOT / ".env")
    # The base domain: from --base, else SAATHI_BASE_DOMAIN, else ask.
    base = (
        args.base
        or env("SAATHI_BASE_DOMAIN")
        or input("Base address (e.g. saathi.example.com): ").strip()
    )
    # The API's address, e.g. https://api.saathi.example.com.
    api = f"https://api.{base}"
    # The Supabase address and its public (anon) key from .env.
    supabase_url, anon_key = env("SUPABASE_URL").rstrip("/"), env("SUPABASE_ANON_KEY")
    # Either missing:
    if not supabase_url or not anon_key:
        # explain what to set...
        print("❌ Set SUPABASE_URL and SUPABASE_ANON_KEY (the publishable key) in .env first.")
        # ...and stop.
        return 1

    # Say what we're testing.
    print(f"Testing {api}\n")
    # One HTTP client for all steps; never follow redirects.
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False) as c:
        # Step 1: is the API up?
        r = c.get(f"{api}/health")
        # Print the result; if it failed...
        if not step(
            # (passed if the status is 200)
            r.status_code == 200,
            # (the label)
            "API is up (GET /health)",
            # (the error, only when it failed)
            error_of(r) if r.status_code != 200 else "",
        ):
            # ...stop.
            return 1

        # Step 2: ask for your login email...
        email = input("Your Supabase login email: ").strip()
        # ...and your password (not shown while typing).
        password = getpass.getpass("Password (hidden): ")
        # Log in to Supabase:
        r = c.post(
            # the token address,
            f"{supabase_url}/auth/v1/token",
            # using email + password,
            params={"grant_type": "password"},
            # with the public key,
            headers={"apikey": anon_key},
            # sending the email and password.
            json={"email": email, "password": password},
        )
        # 🔒 Forget the password straight away.
        del password
        # The login token, if the login worked.
        token = r.json().get("access_token") if r.status_code == 200 else None
        # Print the result; if it failed...
        if not step(
            # (passed if we got a token)
            bool(token),
            # (the label)
            "Logged in with Supabase",
            # (a hint, only when it failed)
            "" if token else f"HTTP {r.status_code}: check email/password",
        ):
            # ...stop.
            return 1
        # Show which algorithm signed the token (never the token itself).
        print(f"   token type: {token_header(token)}  (the API accepts ES256/RS256 only)")
        # The header that proves who we are on every API call.
        auth = {"Authorization": f"Bearer {token}"}

        # Step 3: does the API accept the token and find your workspace?
        r = c.get(f"{api}/api/v1/bots", headers=auth)
        # Print the result; if it failed...
        if not step(
            r.status_code == 200, "Token accepted, workspace found (GET /api/v1/bots)", error_of(r)
        ):
            # 403 means: valid login, but no workspace row for this user...
            if r.status_code == 403:
                # ...so explain the fix.
                print("   -> no workspace for your user yet: run the step-2 SQL.")
            # Stop.
            return 1

        # Step 4: which AI models does your plan allow?
        r = c.get(f"{api}/api/v1/model-options", headers=auth)
        # The list, or empty on error.
        options = r.json() if r.status_code == 200 else []
        # Print the result; if there are none...
        if not step(
            # (passed if the list isn't empty)
            bool(options),
            # (the label)
            "A model is available on your plan (GET /api/v1/model-options)",
            # (the error, or how many options)
            error_of(r) if r.status_code != 200 else f"{len(options)} option(s)",
        ):
            # ...explain the fix...
            print("   -> set GEMINI_MODEL_SMALL in the server's .env, then restart the app.")
            # ...and stop.
            return 1
        # Use the first model for the test configs.
        model_key = options[0]["key"]

        # A unique bot name with the current time.
        name = f"Smoke test {time.strftime('%Y-%m-%d %H:%M:%S')}"
        # Step 5: create a test bot (English + Bengali).
        r = c.post(
            f"{api}/api/v1/bots", headers=auth, json={"name": name, "languages": ["en", "bn"]}
        )
        # Print the result; if it failed...
        if not step(
            # (passed on 201 Created)
            r.status_code == 201,
            # (the label)
            "Created a bot (POST /api/v1/bots)",
            # (the error, or the bot's name)
            error_of(r) if r.status_code != 201 else name,
        ):
            # ...stop.
            return 1
        # The new bot.
        bot = r.json()
        # The address of its config versions.
        base_cfg = f"{api}/api/v1/bots/{bot['id']}/config/versions"
        # Whatever happens next, the `finally` below deletes the bot.
        try:
            # Step 6: save and publish two versions, one after the other:
            for title in ("Smoke v1", "Smoke v2"):
                # a minimal config:
                config = {
                    # branding with a title and a Bengali greeting (tests Unicode),
                    "branding": {"header_title": title, "greeting": "নমস্কার!"},
                    # and the model chosen above.
                    "generation": {"model_key": model_key},
                }
                # Save it as a draft.
                r = c.post(base_cfg, headers=auth, json=config)
                # Print the result; if it failed...
                if not step(
                    # (passed on 201 Created)
                    r.status_code == 201,
                    # (the label)
                    f"Saved draft '{title}' (POST config/versions)",
                    # (the error, or the new version number)
                    error_of(r) if r.status_code != 201 else f"v{r.json().get('version')}",
                ):
                    # ...stop.
                    return 1
                # The draft's version number.
                version = r.json()["version"]
                # Publish it.
                r = c.post(f"{base_cfg}/{version}/publish", headers=auth)
                # Passed if the answer says 'published'.
                ok = r.status_code == 200 and r.json().get("status") == "published"
                # Print the result; stop if it failed.
                if not step(ok, f"Published v{version}", "" if ok else error_of(r)):
                    # Stop.
                    return 1

            # Step 7: read all versions...
            r = c.get(base_cfg, headers=auth)
            # ...and collect the numbers of the published ones.
            live = (
                [v["version"] for v in r.json() if v["status"] == "published"]
                if r.status_code == 200
                else []
            )
            # Exactly one must be live: version 2.
            step(
                # (passed if only v2 is published)
                live == [2],
                # (the label)
                "After publishing twice, exactly one version is live",
                # (what we found)
                f"live versions: {live}",
            )

            # Step 8: read the public widget config, with no login.
            r = c.get(f"{api}/public/v1/widgets/{bot['public_key']}/config")
            # Passed if it shows the newest title.
            ok = r.status_code == 200 and r.json().get("header_title") == "Smoke v2"
            # Print the result:
            step(
                # (passed?)
                ok,
                # (the label)
                "Public widget config shows the published look (no login)",
                # (the error, only when it failed)
                "" if ok else error_of(r),
            )
            # If it worked...
            if ok:
                # 🔒 ...check that no internal field leaked into the public answer...
                leaked = {"bot_id", "persona", "model_key", "plan"} & set(r.json())
                # ...and print the result:
                step(
                    # (passed if nothing leaked)
                    not leaked,
                    # (the label)
                    "Public response contains no internal fields",
                    # (what leaked, if anything)
                    f"unexpected: {sorted(leaked)}" if leaked else "",
                )
        # `finally`: runs even if a step above stopped early, so the test bot is always
        #   cleaned up.
        finally:
            # If --keep was given...
            if args.keep:
                # ...leave the bot and say so.
                print(f"\nKept the test bot '{name}' (--keep).")
            # Otherwise...
            else:
                # ...delete the test bot...
                r = c.delete(f"{api}/api/v1/bots/{bot['id']}", headers=auth)
                # ...and print the result:
                step(
                    # (passed on 204 No Content)
                    r.status_code == 204,
                    # (the label)
                    "Deleted the test bot (DELETE /api/v1/bots/{id})",
                    # (the error, only when it failed)
                    error_of(r) if r.status_code != 204 else "",
                )

    # Print the overall result:
    print(
        "\n"
        + ("❌ Some checks failed - see above." if failed else "✅ Phase 1 live checks passed.")
    )
    # Exit code 1 if anything failed, else 0.
    return 1 if failed else 0


# Only when run directly:
if __name__ == "__main__":
    # Try to run the checks...
    try:
        # ...and exit with their result.
        sys.exit(main())
    # Ctrl+C, or the input ended:
    except (KeyboardInterrupt, EOFError):
        # say 'cancelled'...
        print("\ncancelled.")
        # ...and exit with 1.
        sys.exit(1)

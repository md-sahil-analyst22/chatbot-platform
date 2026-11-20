#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Checks that every API key in your .env really works, by making one tiny harmless call to
#       each vendor.
# Run: make check-keys. Prints OK/FAIL per vendor; never prints the keys themselves.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Phase 0 exit check: verify every configured API key with one cheap call.

Usage (from repo root):
    uv run --with httpx scripts/check_keys.py [--send-whatsapp]

Reads .env from the repo root. Never prints secret values. Exit code 1 if any check fails.
Endpoints are the providers' documented lightweight calls; if one changes, update it here.
"""

# From __future__ — Python language switches: annotations = lets type hints mention classes
#   defined later.
from __future__ import annotations

# argparse — reads command-line options such as --keep.
import argparse
# asyncio — runs many waiting tasks at once (async).
import asyncio
# os — talks to the operating system (environment variables, files).
import os
# sys — Python runtime details (output streams, exit codes).
import sys
# From collections.abc — standard type names for collections: Awaitable = type for something you
#   can `await`; Callable = type for a function.
from collections.abc import Awaitable, Callable
# From pathlib — file and folder paths: Path = a file or folder path.
from pathlib import Path

# httpx — the HTTP client we use to call other web services.
import httpx

# Give every vendor call at most 10 seconds.
TIMEOUT = httpx.Timeout(10.0)
# The repository's top folder.
REPO_ROOT = Path(__file__).resolve().parents[1]


# Read .env into the environment (without overwriting values already set).
def load_dotenv(path: Path) -> None:
    # No .env file...
    if not path.exists():
        # ...then nothing to load.
        return
    # Go through the file line by line:
    for raw in path.read_text(encoding="utf-8").splitlines():
        # trim spaces;
        line = raw.strip()
        # skip blank lines, comment lines and lines without '='...
        if not line or line.startswith("#") or "=" not in line:
            # ...like this.
            continue
        # Split 'NAME=value' at the first '='.
        key, _, value = line.partition("=")
        # Drop a trailing ' # comment' and surrounding quotes.
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        # Set it, unless the variable is already set in the real environment.
        os.environ.setdefault(key.strip(), value)


# One setting's value ('' if missing).
def env(name: str) -> str:
    # The variable's value without spaces ('' if not set).
    return os.environ.get(name, "").strip()


# Type name: a check is an async function that takes the HTTP client and returns a short
#   result.
Check = Callable[[httpx.AsyncClient], Awaitable[str]]


# Each check_* function calls one vendor and returns a short result.
async def check_anthropic(c: httpx.AsyncClient) -> str:
    # GET Anthropic's model list (a harmless read):
    r = await c.get(
        # the address,
        "https://api.anthropic.com/v1/models",
        # with the key and API version headers.
        headers={"x-api-key": env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
    )
    # An error status (e.g. 401 bad key) raises an error.
    r.raise_for_status()
    # Report how many models the key can see.
    return f"{len(r.json().get('data', []))} models visible"


# Check the Gemini key and that the configured models exist.
async def check_gemini(c: httpx.AsyncClient) -> str:
    # GET Gemini's model list:
    r = await c.get(
        # the address,
        "https://generativelanguage.googleapis.com/v1beta/models",
        # with the key header,
        headers={"x-goog-api-key": env("GEMINI_API_KEY")},
        # up to 1000 models in one page.
        params={"pageSize": 1000},
    )
    # An error status raises an error.
    r.raise_for_status()
    # The model names, without the 'models/' prefix.
    names = [m.get("name", "").removeprefix("models/") for m in r.json().get("models", [])]
    # The chat models (for the error message).
    chat = sorted(n for n in names if n.startswith("gemini-") and "embedding" not in n)
    # The models our .env says we use:
    wanted = [
        # the embedding model,
        env("GEMINI_EMBEDDING_MODEL") or "gemini-embedding-2",
        # plus the small and large chat models, if set.
        *(m for m in (env("GEMINI_MODEL_SMALL"), env("GEMINI_MODEL_LARGE")) if m),
    ]
    # Which of them Gemini doesn't offer.
    missing = [m for m in wanted if m not in names]
    # Any missing:
    if missing:
        # Model ids are not secret; print what exists so the right ids can be chosen.
        raise RuntimeError(f"not available: {', '.join(missing)}; chat models: {', '.join(chat)}")
    # All present.
    return f"{', '.join(wanted)} available"


# Check the OpenAI key.
async def check_openai(c: httpx.AsyncClient) -> str:
    # GET OpenAI's model list:
    r = await c.get(
        # the address,
        "https://api.openai.com/v1/models",
        # with the key header.
        headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"},
    )
    # An error status raises an error.
    r.raise_for_status()
    # It worked.
    return "ok"


# Check the Cohere key.
async def check_cohere(c: httpx.AsyncClient) -> str:
    # POST to Cohere's key-check endpoint:
    r = await c.post(
        # the address,
        "https://api.cohere.com/v1/check-api-key",
        # with the key header.
        headers={"Authorization": f"Bearer {env('COHERE_API_KEY')}"},
    )
    # An error status raises an error.
    r.raise_for_status()
    # Cohere says the key isn't valid...
    if not r.json().get("valid", False):
        # ...so fail.
        raise RuntimeError("key reported invalid")
    # It's valid.
    return "valid"


# Check the Sarvam key with a tiny translation.
async def check_sarvam(c: httpx.AsyncClient) -> str:
    # POST to Sarvam:
    r = await c.post(
        # the translate address,
        "https://api.sarvam.ai/translate",
        # with the key header,
        headers={"api-subscription-key": env("SARVAM_API_KEY")},
        # translate 'Hello' from English to Bengali.
        json={"input": "Hello", "source_language_code": "en-IN", "target_language_code": "bn-IN"},
    )
    # An error status raises an error.
    r.raise_for_status()
    # It worked.
    return "translate ok"


# Check that Supabase answers with the public (anon) key.
async def check_supabase(c: httpx.AsyncClient) -> str:
    # GET the Auth settings:
    r = await c.get(
        # <project>/auth/v1/settings,
        f"{env('SUPABASE_URL').rstrip('/')}/auth/v1/settings",
        # with the anon key.
        headers={"apikey": env("SUPABASE_ANON_KEY")},
    )
    # An error status raises an error.
    r.raise_for_status()
    # It worked.
    return "auth settings reachable"


# Check the server-only Supabase key and that both storage buckets exist correctly.
async def check_supabase_storage(c: httpx.AsyncClient) -> str:
    # GET the list of buckets:
    r = await c.get(
        # <project>/storage/v1/bucket,
        f"{env('SUPABASE_URL').rstrip('/')}/storage/v1/bucket",
        # with the secret key headers:
        headers={
            # 🔒 the secret key as a Bearer token,
            "Authorization": f"Bearer {env('SUPABASE_SERVICE_ROLE_KEY')}",
            # and as the apikey header.
            "apikey": env("SUPABASE_SERVICE_ROLE_KEY"),
        },
    )
    # An error status raises an error.
    r.raise_for_status()
    # Bucket name -> is it public?
    buckets = {b.get("name"): b.get("public") for b in r.json()}
    # The buckets we expect:
    wanted = {
        # the private one (must NOT be public),
        env("SUPABASE_STORAGE_PRIVATE_BUCKET") or "documents": False,
        # the public one (must be public).
        env("SUPABASE_STORAGE_PUBLIC_BUCKET") or "public-assets": True,
    }
    # Problems: a bucket is missing or has the wrong visibility.
    problems = [
        f"{name} missing" if name not in buckets else f"{name} should be public={public}"
        for name, public in wanted.items()
        if buckets.get(name) is not public
    ]
    # Any problems...
    if problems:
        # ...fail and list them.
        raise RuntimeError("; ".join(problems))
    # All good.
    return "buckets ok"


# Check the Upstash Redis REST token.
async def check_upstash(c: httpx.AsyncClient) -> str:
    # GET <url>/ping:
    r = await c.get(
        # the address,
        f"{env('UPSTASH_REDIS_REST_URL').rstrip('/')}/ping",
        # with the token header.
        headers={"Authorization": f"Bearer {env('UPSTASH_REDIS_REST_TOKEN')}"},
    )
    # An error status raises an error.
    r.raise_for_status()
    # Redis' answer (PONG).
    return str(r.json().get("result"))


# Check the Langfuse keys.
async def check_langfuse(c: httpx.AsyncClient) -> str:
    # GET the projects list:
    r = await c.get(
        # the address,
        f"{env('LANGFUSE_HOST').rstrip('/')}/api/public/projects",
        # logging in with the public and secret keys.
        auth=(env("LANGFUSE_PUBLIC_KEY"), env("LANGFUSE_SECRET_KEY")),
    )
    # An error status raises an error.
    r.raise_for_status()
    # It worked.
    return "ok"


# Check the WhatsApp token by reading our phone number's details.
async def check_whatsapp_token(c: httpx.AsyncClient) -> str:
    # The Graph API version (default v21.0).
    version = env("WHATSAPP_GRAPH_VERSION") or "v21.0"
    # GET the phone number id:
    r = await c.get(
        # the address,
        f"https://graph.facebook.com/{version}/{env('WHATSAPP_PHONE_NUMBER_ID')}",
        # with the token header.
        headers={"Authorization": f"Bearer {env('WHATSAPP_ACCESS_TOKEN')}"},
    )
    # An error status raises an error.
    r.raise_for_status()
    # It worked.
    return "phone number id readable"


# Optional: actually sends a WhatsApp test message (only with --send-whatsapp).
async def send_whatsapp_hello(c: httpx.AsyncClient) -> str:
    # The Graph API version.
    version = env("WHATSAPP_GRAPH_VERSION") or "v21.0"
    # POST a message:
    r = await c.post(
        # the send address,
        f"https://graph.facebook.com/{version}/{env('WHATSAPP_PHONE_NUMBER_ID')}/messages",
        # with the token header,
        headers={"Authorization": f"Bearer {env('WHATSAPP_ACCESS_TOKEN')}"},
        # sending JSON:
        json={
            # the product name Meta requires,
            "messaging_product": "whatsapp",
            # the test phone number,
            "to": env("WHATSAPP_TEST_RECIPIENT"),
            # a template message,
            "type": "template",
            # Meta's built-in 'hello_world' template in English.
            "template": {"name": "hello_world", "language": {"code": "en_US"}},
        },
    )
    # An error status raises an error.
    r.raise_for_status()
    # It worked.
    return "hello_world template sent - check your phone"


# The checks: (display name, variables it needs, function):
CHECKS: list[tuple[str, tuple[str, ...], Check]] = [
    # Gemini,
    ("Gemini", ("GEMINI_API_KEY",), check_gemini),
    # Anthropic,
    ("Anthropic", ("ANTHROPIC_API_KEY",), check_anthropic),
    # OpenAI,
    ("OpenAI", ("OPENAI_API_KEY",), check_openai),
    # Cohere,
    ("Cohere", ("COHERE_API_KEY",), check_cohere),
    # Sarvam,
    ("Sarvam", ("SARVAM_API_KEY",), check_sarvam),
    # Supabase (public key),
    ("Supabase", ("SUPABASE_URL", "SUPABASE_ANON_KEY"), check_supabase),
    # Supabase Storage (secret key):
    (
        # name,
        "Supabase Storage",
        # needed variables,
        ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"),
        # function;
        check_supabase_storage,
    ),
    # Upstash Redis,
    ("Upstash Redis", ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"), check_upstash),
    # Langfuse,
    ("Langfuse", ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"), check_langfuse),
    # WhatsApp token.
    ("WhatsApp token", ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"), check_whatsapp_token),
]


# Run all checks at the same time and print a table.
async def run(send_whatsapp: bool) -> int:
    # Start from the standard checks.
    checks = list(CHECKS)
    # If --send-whatsapp was given...
    if send_whatsapp:
        # ...add the real test message:
        checks.append(
            # one (name, variables, function) entry:
            (
                # name,
                "WhatsApp send",
                # needed variables,
                ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TEST_RECIPIENT"),
                # function.
                send_whatsapp_hello,
            )
        )

    # Runs one check and returns (name, status, detail).
    async def one(name: str, required: tuple[str, ...], fn: Check) -> tuple[str, str, str]:
        # Variables the check needs but are empty.
        missing = [v for v in required if not env(v)]
        # Any missing:
        if missing:
            # skip this check and say which.
            return name, "SKIP", f"not set: {', '.join(missing)}"
        # Try the check:
        try:
            # with its own HTTP client (closed afterwards),
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                # and report PASS with its result.
                return name, "PASS", await fn(client)
        # The vendor answered with an error status:
        except httpx.HTTPStatusError as exc:
            # FAIL with just the status code (never the response body).
            return name, "FAIL", f"HTTP {exc.response.status_code}"
        except RuntimeError as exc:  # our own messages (bucket names etc.), never secrets
            # FAIL with our own message.
            return name, "FAIL", str(exc)
        except Exception as exc:  # report, never crash the whole run
            # FAIL with just the error's type (never its text, which could contain a key).
            return name, "FAIL", type(exc).__name__

    # Run all checks at the same time and collect the results.
    results = await asyncio.gather(*(one(*c) for c in checks))
    # The longest name, to line up the table.
    width = max(len(r[0]) for r in results)
    # Print one line per check:
    for name, status, detail in results:
        # status, name, detail.
        print(f"{status:<5} {name:<{width}}  {detail}")
    # A reminder about Sentry.
    print("\nSentry: verify in Phase 1 by triggering a test error from the API.")
    # Exit code 1 if any check failed, else 0.
    return 1 if any(r[1] == "FAIL" for r in results) else 0


# Command-line entry point.
def main() -> None:
    # Read command-line options:
    parser = argparse.ArgumentParser()
    # --send-whatsapp switches on the real test message.
    parser.add_argument("--send-whatsapp", action="store_true")
    # Parse them.
    args = parser.parse_args()
    # Load the repository's .env file.
    load_dotenv(REPO_ROOT / ".env")
    # Run the checks and exit with their result.
    sys.exit(asyncio.run(run(args.send_whatsapp)))


# Only when run directly:
if __name__ == "__main__":
    # start main().
    main()

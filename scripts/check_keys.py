#!/usr/bin/env python3
"""Phase 0 exit check: verify every configured API key with one cheap call.

Usage (from repo root):
    uv run --with httpx scripts/check_keys.py [--send-whatsapp]

Reads .env from the repo root. Never prints secret values. Exit code 1 if any check fails.
Endpoints are the providers' documented lightweight calls; if one changes, update it here.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

TIMEOUT = httpx.Timeout(10.0)
REPO_ROOT = Path(__file__).resolve().parents[1]


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


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


Check = Callable[[httpx.AsyncClient], Awaitable[str]]


async def check_anthropic(c: httpx.AsyncClient) -> str:
    r = await c.get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
    )
    r.raise_for_status()
    return f"{len(r.json().get('data', []))} models visible"


async def check_openai(c: httpx.AsyncClient) -> str:
    r = await c.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"},
    )
    r.raise_for_status()
    return "ok"


async def check_cohere(c: httpx.AsyncClient) -> str:
    r = await c.post(
        "https://api.cohere.com/v1/check-api-key",
        headers={"Authorization": f"Bearer {env('COHERE_API_KEY')}"},
    )
    r.raise_for_status()
    if not r.json().get("valid", False):
        raise RuntimeError("key reported invalid")
    return "valid"


async def check_sarvam(c: httpx.AsyncClient) -> str:
    r = await c.post(
        "https://api.sarvam.ai/translate",
        headers={"api-subscription-key": env("SARVAM_API_KEY")},
        json={"input": "Hello", "source_language_code": "en-IN", "target_language_code": "bn-IN"},
    )
    r.raise_for_status()
    return "translate ok"


async def check_supabase(c: httpx.AsyncClient) -> str:
    r = await c.get(
        f"{env('SUPABASE_URL').rstrip('/')}/auth/v1/settings",
        headers={"apikey": env("SUPABASE_ANON_KEY")},
    )
    r.raise_for_status()
    return "auth settings reachable"


async def check_upstash(c: httpx.AsyncClient) -> str:
    r = await c.get(
        f"{env('UPSTASH_REDIS_REST_URL').rstrip('/')}/ping",
        headers={"Authorization": f"Bearer {env('UPSTASH_REDIS_REST_TOKEN')}"},
    )
    r.raise_for_status()
    return str(r.json().get("result"))


async def check_langfuse(c: httpx.AsyncClient) -> str:
    r = await c.get(
        f"{env('LANGFUSE_HOST').rstrip('/')}/api/public/projects",
        auth=(env("LANGFUSE_PUBLIC_KEY"), env("LANGFUSE_SECRET_KEY")),
    )
    r.raise_for_status()
    return "ok"


async def check_whatsapp_token(c: httpx.AsyncClient) -> str:
    version = env("WHATSAPP_GRAPH_VERSION") or "v21.0"
    r = await c.get(
        f"https://graph.facebook.com/{version}/{env('WHATSAPP_PHONE_NUMBER_ID')}",
        headers={"Authorization": f"Bearer {env('WHATSAPP_ACCESS_TOKEN')}"},
    )
    r.raise_for_status()
    return "phone number id readable"


async def send_whatsapp_hello(c: httpx.AsyncClient) -> str:
    version = env("WHATSAPP_GRAPH_VERSION") or "v21.0"
    r = await c.post(
        f"https://graph.facebook.com/{version}/{env('WHATSAPP_PHONE_NUMBER_ID')}/messages",
        headers={"Authorization": f"Bearer {env('WHATSAPP_ACCESS_TOKEN')}"},
        json={
            "messaging_product": "whatsapp",
            "to": env("WHATSAPP_TEST_RECIPIENT"),
            "type": "template",
            "template": {"name": "hello_world", "language": {"code": "en_US"}},
        },
    )
    r.raise_for_status()
    return "hello_world template sent - check your phone"


CHECKS: list[tuple[str, tuple[str, ...], Check]] = [
    ("Anthropic", ("ANTHROPIC_API_KEY",), check_anthropic),
    ("OpenAI", ("OPENAI_API_KEY",), check_openai),
    ("Cohere", ("COHERE_API_KEY",), check_cohere),
    ("Sarvam", ("SARVAM_API_KEY",), check_sarvam),
    ("Supabase", ("SUPABASE_URL", "SUPABASE_ANON_KEY"), check_supabase),
    ("Upstash Redis", ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"), check_upstash),
    ("Langfuse", ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"), check_langfuse),
    ("WhatsApp token", ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"), check_whatsapp_token),
]


async def run(send_whatsapp: bool) -> int:
    checks = list(CHECKS)
    if send_whatsapp:
        checks.append(
            (
                "WhatsApp send",
                ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TEST_RECIPIENT"),
                send_whatsapp_hello,
            )
        )

    async def one(name: str, required: tuple[str, ...], fn: Check) -> tuple[str, str, str]:
        missing = [v for v in required if not env(v)]
        if missing:
            return name, "SKIP", f"not set: {', '.join(missing)}"
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                return name, "PASS", await fn(client)
        except httpx.HTTPStatusError as exc:
            return name, "FAIL", f"HTTP {exc.response.status_code}"
        except Exception as exc:  # report, never crash the whole run
            return name, "FAIL", type(exc).__name__

    results = await asyncio.gather(*(one(*c) for c in checks))
    width = max(len(r[0]) for r in results)
    for name, status, detail in results:
        print(f"{status:<5} {name:<{width}}  {detail}")
    print("\nSentry: verify in Phase 1 by triggering a test error from the API.")
    return 1 if any(r[1] == "FAIL" for r in results) else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send-whatsapp", action="store_true")
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    sys.exit(asyncio.run(run(args.send_whatsapp)))


if __name__ == "__main__":
    main()

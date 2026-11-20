# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Creates the ONE shared HTTP client used to call outside services (Gemini, Supabase,
#       Sarvam...).
# Why: One client reuses connections and applies the same safety settings everywhere.
# Security: 🔒 Never follows redirects, so a vendor response can't send us to an unexpected
#           (internal) address.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""One outbound HTTP client per process, owned and closed by the container.

Adapters receive it via constructor injection; they never create or close clients themselves.
"""

import httpx


# Timeouts (10 s, 3 s to connect), max 100 connections, no redirects.
def build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=3.0),  # adapters pass tighter per-call timeouts
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=False,  # never follow redirects to unexpected hosts (SSRF hygiene)
    )

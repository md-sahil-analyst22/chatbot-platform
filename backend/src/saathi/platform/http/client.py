"""One outbound HTTP client per process, owned and closed by the container.

Adapters receive it via constructor injection; they never create or close clients themselves.
"""

import httpx


def build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=3.0),  # adapters pass tighter per-call timeouts
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=False,  # never follow redirects to unexpected hosts (SSRF hygiene)
    )

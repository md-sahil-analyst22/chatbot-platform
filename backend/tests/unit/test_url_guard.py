# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 SSRF protection for tenant-supplied URLs: private/loopback/metadata
#                addresses are refused, every DNS answer is checked, the connection is pinned to
#                the checked IP, redirects are not followed and bodies are capped.
# How to run: cd backend && uv run pytest tests/unit/test_url_guard.py (no network: DNS and HTTP
#             are faked).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""platform/http/url_guard.py."""

# asyncio — gives access to the running event loop (whose DNS lookup we fake).
import asyncio

# socket — constants for the fake DNS answers (IPv4, TCP).
import socket

# From typing — type-hint helpers: Any = any type.
from typing import Any

# httpx — the HTTP client; MockTransport answers requests without a network.
import httpx

# pytest — the test framework.
import pytest

# From saathi.platform.errors — our error types: ValidationError = 422 invalid/unsafe input.
from saathi.platform.errors import ValidationError

# From saathi.platform.http — the module under test (to call resolve_public_ip by name).
from saathi.platform.http import url_guard

# From saathi.platform.http.url_guard — SSRF guard: fetch_public_url = one safe GET;
#   is_public_ip = public internet address?; parse_public_url = URL shape check.
from saathi.platform.http.url_guard import fetch_public_url, is_public_ip, parse_public_url


# Each pair is (address, is it a normal public internet address?).
@pytest.mark.parametrize(
    ("ip", "public"),
    [
        # Public IPv4.
        ("8.8.8.8", True),
        # Public IPv6.
        ("2606:4700::1111", True),
        # Private ranges.
        ("10.0.0.5", False),
        ("192.168.1.1", False),
        ("172.16.0.1", False),
        # This machine.
        ("127.0.0.1", False),
        ("169.254.169.254", False),  # cloud metadata
        # This machine (IPv6).
        ("::1", False),
        ("::ffff:10.0.0.1", False),  # IPv4-mapped private
        ("fd00::1", False),  # unique local
        ("224.0.0.1", False),  # multicast
        ("0.0.0.0", False),  # noqa: S104 - test data, not a bind address
        # Not an address at all.
        ("not-an-ip", False),
    ],
)
# Only normal internet addresses count as public.
def test_public_ip_classification(ip: str, public: bool) -> None:
    # The guard agrees with the table.
    assert is_public_ip(ip) is public


# Each of these URLs has an unsafe shape.
@pytest.mark.parametrize(
    "url",
    [
        # Local files.
        "file:///etc/passwd",
        # Old protocol often used in SSRF attacks.
        "gopher://a.in/",
        # Credentials in the address.
        "http://user:pw@a.in/",
        # A non-web port (Redis).
        "http://a.in:6379/",
        # No host.
        "https:///nohost",
        # Far too long.
        "https://" + "a" * 2001 + ".in",
    ],
)
# Unsafe URL shapes are refused before any network activity.
def test_unsafe_url_shapes_are_refused(url: str) -> None:
    # 422...
    with pytest.raises(ValidationError):
        # ...from the shape check.
        parse_public_url(url)


# Make the event loop's DNS lookup return chosen addresses.
def _fake_dns(monkeypatch: pytest.MonkeyPatch, addresses: list[str]) -> None:
    # The fake lookup...
    async def fake_getaddrinfo(host: str, port: int, **kwargs: Any) -> list[Any]:
        # ...one answer per address, in getaddrinfo's shape.
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses]

    # Swap it in for this test only (monkeypatch undoes it afterwards).
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)


# 🔒 A name that resolves to a public AND a private address is refused (rebinding trick).
async def test_any_private_dns_answer_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # DNS answers with one public and one private address.
    _fake_dns(monkeypatch, ["93.184.216.34", "10.0.0.7"])
    # Refused with the 'private' message...
    with pytest.raises(ValidationError, match="private"):
        # ...when resolving.
        await url_guard.resolve_public_ip("evil.example", 443)


# 🔒 The request goes to the checked IP, while Host and TLS use the real name.
async def test_fetch_connects_to_the_checked_ip_with_the_real_host_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DNS gives one public address.
    _fake_dns(monkeypatch, ["93.184.216.34"])
    # What the fake server saw.
    seen: dict[str, Any] = {}

    # The fake server records the request.
    def handler(request: httpx.Request) -> httpx.Response:
        # The host actually connected to.
        seen["host"] = request.url.host
        # The Host header sent.
        seen["host_header"] = request.headers["host"]
        # The name TLS would verify.
        seen["sni"] = request.extensions.get("sni_hostname")
        # A small HTML page.
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="ok")

    # A client that talks to the fake server.
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    # Fetch through the guard.
    page = await fetch_public_url(
        http, "https://shop.example/a", max_bytes=100, timeout_s=1, user_agent="t"
    )
    # Connected to the pinned IP; Host header and TLS name are the real host.
    assert seen == {"host": "93.184.216.34", "host_header": "shop.example", "sni": "shop.example"}
    # The page reports the original address and the content type without '; charset'.
    assert page.url == "https://shop.example/a" and page.content_type == "text/html"


# 🔒 A redirect is reported, never followed automatically.
async def test_redirects_are_returned_not_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    # DNS gives one public address.
    _fake_dns(monkeypatch, ["93.184.216.34"])
    # A fake server that redirects to the cloud metadata address.
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(302, headers={"location": "http://169.254.169.254/"})
        )
    )
    # Fetch through the guard.
    page = await fetch_public_url(
        http, "http://a.example/", max_bytes=10, timeout_s=1, user_agent="t"
    )
    # We get the redirect itself (the caller must check its target again).
    assert page.status == 302 and page.location == "http://169.254.169.254/"


# 🔒 Bodies are cut at the size limit.
async def test_body_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    # DNS gives one public address.
    _fake_dns(monkeypatch, ["93.184.216.34"])
    # A fake server that sends 1 MB.
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 1_000_000))
    )
    # Fetch with a 1 KB limit.
    page = await fetch_public_url(
        http, "http://a.example/", max_bytes=1024, timeout_s=1, user_agent="t"
    )
    # Exactly 1 KB kept, marked as cut.
    assert len(page.body) == 1024 and page.truncated

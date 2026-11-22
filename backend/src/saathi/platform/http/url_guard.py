# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Safe fetching of web addresses that a TENANT gave us (website crawler).
# Why: Without checks, a tenant could ask our server to fetch 'http://169.254.169.254/' (cloud
#      secrets) or 'http://localhost:6379' (our Redis). This is called SSRF.
# How: 1. only http/https on the normal ports, no 'user:password@' in the address;
#      2. look up the host name ourselves and refuse if ANY address is private/loopback/etc.;
#      3. connect to exactly that checked IP (so a second DNS answer can't swap it - 'DNS
#         rebinding'), while TLS still checks the real host name's certificate;
#      4. never follow redirects automatically; cap the size and the time of every response.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SSRF-safe GET for tenant-supplied URLs (crawler, later: custom webhook tools)."""

# asyncio — runs DNS lookups without blocking the event loop (R32).
import asyncio

# ipaddress — understands IPv4/IPv6 addresses and which ranges are private.
import ipaddress

# socket — constants for the DNS lookup (TCP only).
import socket

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# httpx — the async HTTP client shared by the whole process.
import httpx

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError

# Only the normal web ports (fail closed: internal services usually listen elsewhere).
ALLOWED_PORTS = frozenset({80, 443})
# Longest address we accept.
MAX_URL_CHARS = 2000


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# What came back from one safe fetch.
class FetchedPage:
    # The address we asked for (as given, not the IP we connected to).
    url: str
    # HTTP status code (200, 301, 404...).
    status: int
    # The Content-Type header, lower case, without parameters ('text/html').
    content_type: str
    # The Location header of a redirect (None otherwise). NOT followed automatically.
    location: str | None
    # The body, at most max_bytes long.
    body: bytes
    # True if the body was cut off at max_bytes.
    truncated: bool


# Is this IP address safe to connect to (a normal internet address)?
def is_public_ip(address: str) -> bool:
    """False for private, loopback, link-local (cloud metadata), multicast, reserved, etc."""
    # Parse it; anything unparseable is not safe.
    try:
        # e.g. IPv4Address('10.0.0.1').
        ip = ipaddress.ip_address(address)
    # Not an IP at all.
    except ValueError:
        # Unsafe.
        return False
    # IPv6 addresses that wrap an IPv4 address ('::ffff:10.0.0.1') are judged by the inner one.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        # Use the wrapped IPv4 address.
        ip = ip.ipv4_mapped
    # is_global is False for every private/reserved/loopback/link-local range; multicast is
    #   excluded explicitly because a few multicast ranges count as 'global'.
    return ip.is_global and not ip.is_multicast


# Check the shape of a URL before any network activity.
def parse_public_url(raw: str) -> httpx.URL:
    """Raise ValidationError unless the URL is http(s), on port 80/443, without credentials."""
    # Too long -> refuse.
    if len(raw) > MAX_URL_CHARS:
        # 422.
        raise ValidationError("URL is too long")
    # Parse it.
    try:
        # httpx's parser (same one that will send the request).
        url = httpx.URL(raw)
    # Unparseable.
    except (httpx.InvalidURL, ValueError):
        # 422.
        raise ValidationError("invalid URL") from None
    # Only web addresses.
    if url.scheme not in ("http", "https"):
        # 422.
        raise ValidationError("URL must start with http:// or https://")
    # A host name is required.
    if not url.host:
        # 422.
        raise ValidationError("URL must contain a host name")
    # 🔒 'user:password@host' is refused (credentials must never travel in URLs).
    if url.userinfo:
        # 422.
        raise ValidationError("URL must not contain a user name or password")
    # The port (default 80/443 when not written).
    port = url.port or (443 if url.scheme == "https" else 80)
    # 🔒 Normal web ports only.
    if port not in ALLOWED_PORTS:
        # 422.
        raise ValidationError("URL must use the standard port 80 or 443")
    # Safe to try.
    return url


# Look a host name up and return ONE checked public IP address.
async def resolve_public_ip(host: str, port: int) -> str:
    """Every address the name resolves to must be public; otherwise refuse (fail closed)."""
    # Do the DNS lookup in the event loop's thread pool (never blocks other requests).
    try:
        # All (family, type, proto, canonname, sockaddr) answers for TCP.
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    # The name doesn't exist.
    except OSError:
        # 422 (the tenant typed a wrong address).
        raise ValidationError("could not resolve the URL's host name") from None
    # The IP strings (first item of each sockaddr).
    addresses = [str(info[4][0]) for info in infos]
    # 🔒 No answers, or ANY private answer -> refuse. Checking all answers stops a name that
    #   resolves to both a public and a private address from sneaking through.
    if not addresses or not all(is_public_ip(a) for a in addresses):
        # 422 without echoing the address.
        raise ValidationError("URL points to a private or reserved network address")
    # Use the first checked address.
    return addresses[0]


# GET a tenant-supplied URL safely.
async def fetch_public_url(
    http: httpx.AsyncClient,
    raw_url: str,
    *,
    max_bytes: int,
    timeout_s: float,
    user_agent: str,
) -> FetchedPage:
    """One GET, pinned to a checked IP, no redirects followed, body capped at max_bytes.

    Raises ValidationError for unsafe URLs and httpx errors for network problems (the caller
    decides whether a failed page matters).
    """
    # Shape check first (no network yet).
    url = parse_public_url(raw_url)
    # The port we'll connect to.
    port = url.port or (443 if url.scheme == "https" else 80)
    # DNS + public-address check.
    ip = await resolve_public_ip(url.host, port)
    # Connect to the IP itself, so the address can't change between check and connect.
    pinned = url.copy_with(host=ip)
    # The Host header carries the real name (virtual hosting), with the port if non-default.
    host_header = url.host if url.port is None else f"{url.host}:{url.port}"
    # For https, TLS must still present and verify the REAL host name (SNI + certificate).
    extensions = {"sni_hostname": url.host} if url.scheme == "https" else {}
    # Stream the response so we can stop reading at max_bytes.
    async with http.stream(
        "GET",
        pinned,
        headers={"Host": host_header, "User-Agent": user_agent, "Accept": "*/*"},
        extensions=extensions,
        timeout=httpx.Timeout(timeout_s, connect=min(timeout_s, 3.0)),
        follow_redirects=False,  # 🔒 a redirect target must pass these checks again
    ) as response:
        # Collect at most max_bytes.
        chunks: list[bytes] = []
        # How many bytes so far.
        size = 0
        # Whether we stopped early.
        truncated = False
        # Read the body piece by piece...
        async for chunk in response.aiter_bytes():
            # ...stop once the limit would be passed.
            if size + len(chunk) > max_bytes:
                # Keep only what fits.
                chunks.append(chunk[: max_bytes - size])
                # Remember it was cut.
                truncated = True
                # Stop reading (closing the stream drops the rest).
                break
            # Keep the piece.
            chunks.append(chunk)
            # Count it.
            size += len(chunk)
        # 'text/html; charset=utf-8' -> 'text/html'.
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        # Return what we got.
        return FetchedPage(
            url=str(url),
            status=response.status_code,
            content_type=content_type,
            location=response.headers.get("location"),
            body=b"".join(chunks),
            truncated=truncated,
        )

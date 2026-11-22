# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The website crawler (P2.4) against a fake website (no network): depth limit,
#                page budget, same-site rule, include/exclude patterns, robots.txt, redirects,
#                sitemaps, and fail-closed behaviour when the site or robots.txt is broken.
# How to run: cd backend && uv sync --extra ingestion &&
#             uv run pytest tests/unit/test_http_crawler.py
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""HttpCrawler adapter."""

# httpx — the HTTP client; MockTransport plays the fake website.
import httpx

# pytest — the test framework.
import pytest

# From saathi.modules.knowledge.adapters.crawlers.http_crawler — the crawler: CrawlerSettings =
#   its options; HttpCrawler = the crawler; path_allowed = include/exclude pattern check.
from saathi.modules.knowledge.adapters.crawlers.http_crawler import (
    CrawlerSettings,
    HttpCrawler,
    path_allowed,
)

# From saathi.modules.knowledge.domain.crawl — crawl settings: CrawlOptions.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.platform.errors — our error types: ProviderError = the website failed;
#   ValidationError = 422 invalid/unsafe input.
from saathi.platform.errors import ProviderError, ValidationError

# From saathi.platform.http — the SSRF guard module (its DNS step is faked here).
from saathi.platform.http import url_guard


# An HTML page with a title, a paragraph long enough for main-text extraction, and links.
def _page(title: str, links: list[str]) -> str:
    # One <a> per link.
    anchors = "".join(f'<a href="{href}">{href}</a> ' for href in links)
    # A paragraph long enough for trafilatura to treat as main text.
    body = f"{title} page. " + "This paragraph explains our services in useful detail. " * 6
    # The page: title, links in a <nav>, content in an <article>.
    return (
        f"<html><head><title>{title}</title></head><body><nav>{anchors}</nav>"
        f"<article><h1>{title}</h1><p>{body}</p></article></body></html>"
    )


# The fake site: path -> (status, headers, body).
SITE: dict[str, tuple[int, dict[str, str], str]] = {
    # robots.txt forbids /private.
    "/robots.txt": (200, {"content-type": "text/plain"}, "User-agent: *\nDisallow: /private\n"),
    # Home links to: A, B (a redirect), another site, a forbidden page and an image.
    "/": (
        200,
        {"content-type": "text/html"},
        _page("Home", ["/a", "/b", "https://other.example/x", "/private/p", "/logo.png"]),
    ),
    # A links one level deeper.
    "/a": (200, {"content-type": "text/html"}, _page("A", ["/a/deep"])),
    # Two clicks away from home.
    "/a/deep": (200, {"content-type": "text/html"}, _page("Deep", [])),
    # A permanent redirect to C.
    "/b": (301, {"location": "/c"}, ""),
    # The redirect target.
    "/c": (200, {"content-type": "text/html"}, _page("C", [])),
    # Forbidden by robots.txt.
    "/private/p": (200, {"content-type": "text/html"}, _page("Secret", [])),
    # A sitemap listing A and C.
    "/sitemap.xml": (
        200,
        {"content-type": "application/xml"},
        "<urlset><url><loc>https://shop.example/a</loc></url>"
        "<url><loc>https://shop.example/c</loc></url></urlset>",
    ),
}


# A crawler wired to the fake site, plus the list of paths it requested.
@pytest.fixture
def crawler(monkeypatch: pytest.MonkeyPatch) -> tuple[HttpCrawler, list[str]]:
    # Every host 'resolves' to one public address (no real DNS)...
    async def fake_resolve(host: str, port: int) -> str:
        # ...always the same one.
        return "93.184.216.34"

    # Swap in the fake DNS step for this test.
    monkeypatch.setattr(url_guard, "resolve_public_ip", fake_resolve)
    # Paths requested, in order.
    requested: list[str] = []

    # The fake server (only shop.example exists).
    def handler(request: httpx.Request) -> httpx.Response:
        # Record host + path.
        requested.append(f"{request.headers['host']}{request.url.path}")
        # Any other host: not found.
        if request.headers["host"] != "shop.example":
            # 404.
            return httpx.Response(404)
        # Look the path up (404 if unknown).
        status, headers, body = SITE.get(request.url.path, (404, {}, ""))
        # Answer.
        return httpx.Response(status, headers=headers, text=body)

    # A client that talks to the fake server.
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    # No politeness delay in tests.
    return HttpCrawler(http, CrawlerSettings(delay_seconds=0)), requested


# Same site only, within depth, redirects followed, forbidden paths and images skipped.
async def test_crawls_same_site_within_depth_and_follows_redirects(
    crawler: tuple[HttpCrawler, list[str]],
) -> None:
    # The crawler and its request log.
    c, requested = crawler
    # Crawl one click deep, up to 10 pages.
    pages = await c.crawl(CrawlOptions("https://shop.example/", max_depth=1, max_pages=10))
    # The addresses collected.
    urls = {p.url for p in pages}
    # Home, A and the redirect target C (not the depth-2 page).
    assert urls == {"https://shop.example/", "https://shop.example/a", "https://shop.example/c"}
    # The other site, the robots-forbidden path and the image were never requested.
    assert not any("other.example" in r or "/private" in r or "logo.png" in r for r in requested)
    # Page titles are kept as headings for the chunker.
    assert next(p for p in pages if p.url.endswith("/a")).text.startswith("# A")


# The page budget and the exclude patterns are respected.
async def test_page_budget_and_exclude_patterns(crawler: tuple[HttpCrawler, list[str]]) -> None:
    # The crawler (request log not needed).
    c, _ = crawler
    # A one-page budget...
    pages = await c.crawl(CrawlOptions("https://shop.example/", max_depth=2, max_pages=1))
    # ...gives only the start page.
    assert [p.url for p in pages] == ["https://shop.example/"]
    # Excluding '/a*'...
    pages = await c.crawl(
        CrawlOptions("https://shop.example/", max_depth=2, exclude_patterns=("/a*",))
    )
    # ...keeps A and Deep out.
    assert not any("/a" in p.url for p in pages)


# A sitemap start reads the pages it lists.
async def test_sitemap_start_reads_listed_pages(crawler: tuple[HttpCrawler, list[str]]) -> None:
    # The crawler.
    c, _ = crawler
    # Start from the sitemap.
    pages = await c.crawl(CrawlOptions("https://shop.example/sitemap.xml"))
    # Exactly the two listed pages.
    assert {p.url for p in pages} == {"https://shop.example/a", "https://shop.example/c"}


# 🔒 If robots.txt can't be read because the site is failing, we don't crawl.
async def test_robots_server_error_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fake DNS...
    async def fake_resolve(host: str, port: int) -> str:
        # ...one public address.
        return "93.184.216.34"

    # Swap it in.
    monkeypatch.setattr(url_guard, "resolve_public_ip", fake_resolve)
    # A site that answers 503 to everything (incl. robots.txt).
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    # A provider error (the job may retry later)...
    with pytest.raises(ProviderError):
        # ...from the crawl.
        await HttpCrawler(http, CrawlerSettings(delay_seconds=0)).crawl(
            CrawlOptions("https://shop.example/")
        )


# A site with nothing readable gets a clear, permanent message (no pointless retries).
async def test_nothing_readable_is_a_clear_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fake DNS...
    async def fake_resolve(host: str, port: int) -> str:
        # ...one public address.
        return "93.184.216.34"

    # Swap it in.
    monkeypatch.setattr(url_guard, "resolve_public_ip", fake_resolve)
    # robots.txt missing (crawling allowed), but every page is 404.
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    # The safe 'No readable page' message...
    with pytest.raises(ValidationError, match="No readable page"):
        # ...from the crawl.
        await HttpCrawler(http, CrawlerSettings(delay_seconds=0)).crawl(
            CrawlOptions("https://shop.example/")
        )


# 🔒 A start address on this machine is refused before any request is made.
async def test_private_start_address_is_refused_before_any_request() -> None:
    # 'localhost' resolves to loopback for real; the guard refuses it.
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    # Refused (as unsafe input or as an unreachable site)...
    with pytest.raises((ProviderError, ValidationError)):
        # ...by the crawl.
        await HttpCrawler(http, CrawlerSettings(delay_seconds=0)).crawl(
            CrawlOptions("http://localhost/")
        )


# Exclude patterns win; no include patterns means 'everything'.
def test_path_patterns() -> None:
    # Matches an include pattern.
    assert path_allowed("/services/gst", ("/services/*",), ())
    # Doesn't match the include pattern.
    assert not path_allowed("/blog/1", ("/services/*",), ())
    # Excluded.
    assert not path_allowed("/services/old", (), ("/services/old",))
    # No patterns at all: allowed.
    assert path_allowed("/anything", (), ())

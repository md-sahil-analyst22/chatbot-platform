# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The website crawler (P2.4). Implements WebCrawler.
# How:
#   - Start address = a normal page (follow links up to max_depth clicks away) or a sitemap
#     (an address ending in .xml: read the page list from it).
#   - Stays on the same site (same host, with or without 'www.'), applies include/exclude path
#     patterns, stops at max_pages.
#   - 🔒 Every request goes through platform/http/url_guard.py: public addresses only, pinned IP,
#     no automatic redirects, size and time limits (SSRF protection).
#   - Respects robots.txt for our user agent. If robots.txt can't be read because the site is
#     failing (5xx/network), we don't crawl (fail closed); a missing robots.txt allows crawling.
#   - Extracts each page's main text as light markdown with trafilatura (menus, footers and ads
#     are dropped). trafilatura's own downloader is never used: we only hand it the HTML.
# Why not Crawl4AI: it needs a headless browser (~1 GB); see REPO_STRUCTURE §4.8. JavaScript-only
#   sites therefore yield little text with this crawler.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""HTTP crawler adapter (P2.4). Requires the 'ingestion' extra (trafilatura)."""

# asyncio — a short pause between requests (politeness).
import asyncio

# fnmatch — shell-style path patterns ('/services/*').
import fnmatch

# re — regular expressions (sitemap <loc> entries).
import re

# From collections import deque = a fast first-in-first-out queue (breadth-first crawl).
from collections import deque

# From html.parser — the standard library's tolerant HTML reader: HTMLParser = base class.
from html.parser import HTMLParser

# From urllib.parse — URL helpers: urldefrag = drop '#section'; urljoin = resolve relative
#   links; urlsplit = split a URL into parts.
from urllib.parse import urldefrag, urljoin, urlsplit

# From urllib.robotparser — robots.txt rules: RobotFileParser = reads and applies them.
from urllib.robotparser import RobotFileParser

# httpx — the async HTTP client shared by the whole process.
import httpx

# structlog — structured logging (JSON log lines).
import structlog

# From pydantic_settings — reads settings from environment variables: BaseSettings = parent
#   class for a settings object; SettingsConfigDict = settings options such as the env prefix.
from pydantic_settings import BaseSettings, SettingsConfigDict

# From saathi.modules.knowledge.adapters — registries: crawler_registry = website crawlers.
from saathi.modules.knowledge.adapters import crawler_registry

# From saathi.modules.knowledge.domain.crawl — crawl settings: CrawlOptions = one crawl's settings.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.ports.providers — crawler contract: CrawledPage = one page's text.
from saathi.modules.knowledge.ports.providers import CrawledPage

# From saathi.platform.errors — our error types: ProviderError = the website failed;
#   ValidationError = 422 invalid/unsafe input.
from saathi.platform.errors import ProviderError, ValidationError

# From saathi.platform.http.url_guard — SSRF-safe fetching: FetchedPage = one response;
#   fetch_public_url = one safe GET; parse_public_url = shape check.
from saathi.platform.http.url_guard import FetchedPage, fetch_public_url, parse_public_url

# The logger for this file.
log = structlog.get_logger()

# <loc>https://...</loc> entries in a sitemap (no XML parser: nothing to exploit, bounded input).
_SITEMAP_LOC = re.compile(r"<loc>\s*([^<\s]{1,2000})\s*</loc>", re.I)
# Content types we read as HTML.
_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
# At most this many nested sitemaps are read from a sitemap index.
_MAX_NESTED_SITEMAPS = 5
# File types never worth fetching as pages.
_SKIP_SUFFIXES = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".css",
    ".js",
    ".zip",
    ".pdf",
    ".mp4",
    ".mp3",
    ".woff",
    ".woff2",
    ".xml",
)


# Settings read from CRAWLER_* environment variables (R12: the adapter owns its settings).
class CrawlerSettings(BaseSettings):
    # Read CRAWLER_* variables from the environment / .env file.
    model_config = SettingsConfigDict(env_prefix="CRAWLER_", env_file=".env", extra="ignore")

    # How we introduce ourselves to websites (robots.txt rules are matched against this).
    user_agent: str = "SaathiBot/1.0 (+knowledge-base crawler)"
    # Time limit per request.
    page_timeout_seconds: float = 10.0
    # Size limit per response (2 MB).
    max_page_bytes: int = 2 * 1024 * 1024
    # Pause between requests to the same site.
    delay_seconds: float = 0.25


# Collects <a href> links and the <title> from an HTML page.
class _LinkAndTitleParser(HTMLParser):
    # Start with nothing collected.
    def __init__(self) -> None:
        # Let the base class set itself up.
        super().__init__(convert_charrefs=True)
        # The links found.
        self.links: list[str] = []
        # Title text pieces.
        self._title: list[str] = []
        # True while inside <title>.
        self._in_title = False

    # Called for every opening tag.
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # A link: keep its href.
        if tag == "a":
            # Find href among the attributes.
            for name, value in attrs:
                # Keep it if present.
                if name == "href" and value:
                    # Remember it.
                    self.links.append(value)
        # The page title starts.
        elif tag == "title":
            # Start collecting.
            self._in_title = True

    # Called for every closing tag.
    def handle_endtag(self, tag: str) -> None:
        # The page title ends.
        if tag == "title":
            # Stop collecting.
            self._in_title = False

    # Called for text between tags.
    def handle_data(self, data: str) -> None:
        # Only text inside <title> matters here.
        if self._in_title:
            # Collect it.
            self._title.append(data)

    # @property: read it like a field.
    @property
    # The page title, tidied.
    def title(self) -> str:
        # Joined, single-spaced, bounded.
        return " ".join("".join(self._title).split())[:300]


# Same site? ('example.com' and 'www.example.com' count as the same.)
def _same_site(host: str, root_host: str) -> bool:
    # Compare without a leading 'www.'.
    return host.lower().removeprefix("www.") == root_host.lower().removeprefix("www.")


# Does a path pass the include/exclude patterns?
def path_allowed(path: str, include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    """Excluded if any exclude pattern matches; otherwise included if no include patterns are
    set or any include pattern matches."""
    # Exclusions win.
    if any(fnmatch.fnmatchcase(path, p) for p in exclude):
        # Skip it.
        return False
    # No include list = everything else is in.
    return not include or any(fnmatch.fnmatchcase(path, p) for p in include)


# The crawler.
class HttpCrawler:
    """Implements WebCrawler with the shared HTTP client and the SSRF guard."""

    # Keep the shared client and settings.
    def __init__(self, http: httpx.AsyncClient, settings: CrawlerSettings | None = None) -> None:
        # Shared client (owned and closed by the container, R11).
        self._http = http
        # Settings (defaults in tests).
        self._s = settings or CrawlerSettings()

    # One safe GET with our limits.
    async def _get(self, url: str) -> FetchedPage:
        # Through the SSRF guard.
        return await fetch_public_url(
            self._http,
            url,
            max_bytes=self._s.max_page_bytes,
            timeout_s=self._s.page_timeout_seconds,
            user_agent=self._s.user_agent,
        )

    # Read the site's robots.txt rules.
    async def _robots(self, root: httpx.URL) -> RobotFileParser:
        # Rules object.
        rules = RobotFileParser()
        # robots.txt lives at the site root.
        robots_url = f"{root.scheme}://{root.netloc.decode()}/robots.txt"
        # Fetch it.
        try:
            # One safe GET.
            page = await self._get(robots_url)
        # The site isn't reachable: fail closed.
        except (httpx.HTTPError, ValidationError):
            # Refuse to crawl.
            raise ProviderError("the website could not be reached") from None
        # Found: apply its rules.
        if page.status == 200:
            # Parse the lines.
            rules.parse(page.body.decode("utf-8", errors="replace").splitlines())
        # Missing (4xx): everything is allowed (the robots.txt convention).
        elif 400 <= page.status < 500:
            # Allow all.
            rules.parse([])
        # Server error / redirect: fail closed (the convention says 'assume disallowed').
        else:
            # Refuse to crawl.
            raise ProviderError("the website's robots.txt could not be read")
        # The rules.
        return rules

    # Read page addresses from a sitemap (and a few nested sitemaps).
    async def _sitemap_urls(self, sitemap_url: str, limit: int) -> list[str]:
        # Addresses found, in order, no duplicates.
        found: list[str] = []
        # Sitemaps still to read.
        pending = [sitemap_url]
        # Sitemaps read so far.
        read = 0
        # Read until done or limits hit.
        while pending and read <= _MAX_NESTED_SITEMAPS and len(found) < limit:
            # Count it.
            read += 1
            # Fetch the next sitemap; an unreachable or unsafe one is skipped.
            try:
                # One safe GET.
                page = await self._get(pending.pop(0))
            # Network trouble or an unsafe address.
            except (httpx.HTTPError, ValidationError):
                # Next sitemap.
                continue
            # Skip failures.
            if page.status != 200:
                # Next.
                continue
            # Every <loc> entry...
            for loc in _SITEMAP_LOC.findall(page.body.decode("utf-8", errors="replace")):
                # ...a nested sitemap goes to the reading list...
                if loc.lower().endswith(".xml"):
                    # Read it later.
                    pending.append(loc)
                # ...a page address is kept (once).
                elif loc not in found:
                    # Keep it.
                    found.append(loc)
        # At most `limit` addresses.
        return found[:limit]

    # Crawl a website within the options' limits.
    async def crawl(self, options: CrawlOptions) -> list[CrawledPage]:
        # trafilatura — extracts a page's main text.
        import trafilatura  # lazy: only the worker image needs this dependency

        # 🔒 Shape check of the start address (422 for unsafe ones).
        root = parse_public_url(options.root_url)
        # robots.txt rules (ProviderError if the site is down).
        robots = await self._robots(root)
        # The queue of (address, depth) to visit.
        queue: deque[tuple[str, int]] = deque()
        # A sitemap start: its pages, all at depth 0 (no link following).
        if root.path.lower().endswith(".xml"):
            # Every listed page.
            for url in await self._sitemap_urls(str(root), options.max_pages * 2):
                # Queue it.
                queue.append((url, options.max_depth))
        # A normal start page.
        else:
            # Start there.
            queue.append((str(root), 0))
        # Addresses already queued or visited.
        seen = {u for u, _ in queue}
        # The pages we collected.
        pages: list[CrawledPage] = []
        # 🔒 Hard bound on requests (redirects and failures count too).
        budget = options.max_pages * 3
        # Breadth-first: nearest pages first.
        while queue and len(pages) < options.max_pages and budget > 0:
            # Next address and its depth.
            url, depth = queue.popleft()
            # Spend one request.
            budget -= 1
            # Its parts.
            parts = urlsplit(url)
            # Off-site, disallowed by patterns or robots.txt: skip without fetching.
            if (
                not _same_site(parts.hostname or "", root.host)
                or not path_allowed(
                    parts.path or "/", options.include_patterns, options.exclude_patterns
                )
                or not robots.can_fetch(self._s.user_agent, url)
            ):
                # Next address.
                continue
            # Be polite between requests.
            if self._s.delay_seconds > 0:
                # Short pause.
                await asyncio.sleep(self._s.delay_seconds)
            # Fetch the page.
            try:
                # One safe GET.
                page = await self._get(url)
            # Network trouble or an unsafe address: skip this page.
            except (httpx.HTTPError, ValidationError) as exc:
                # Log the type only.
                log.info("crawl.page_skipped", error_type=type(exc).__name__)
                # Next address.
                continue
            # A redirect: queue its target (checked again when fetched), same depth.
            if 300 <= page.status < 400 and page.location:
                # Absolute address without '#fragment'.
                target = urldefrag(urljoin(url, page.location))[0]
                # Queue it once.
                if target not in seen:
                    # Remember and queue.
                    seen.add(target)
                    # Same depth (a redirect is not a click).
                    queue.append((target, depth))
                # Next address.
                continue
            # Errors and non-text pages: skip.
            if page.status != 200 or page.content_type not in (*_HTML_TYPES, "text/plain"):
                # Next address.
                continue
            # Plain text: use as-is.
            if page.content_type == "text/plain":
                # Decode leniently.
                pages.append(
                    CrawledPage(url=url, title="", text=page.body.decode("utf-8", errors="replace"))
                )
                # Next address.
                continue
            # HTML: links and title (lenient parser; broken HTML never raises).
            html_text = page.body.decode("utf-8", errors="replace")
            # Our link/title collector.
            collector = _LinkAndTitleParser()
            # Feed it the page.
            collector.feed(html_text)
            # Main text as markdown (headings kept, tables kept, links dropped).
            text = trafilatura.extract(
                html_text,
                output_format="markdown",
                include_tables=True,
                include_links=False,
                include_comments=False,
                favor_recall=True,
            )
            # Keep pages with text.
            if text and text.strip():
                # Title as a top heading, then the text.
                title = collector.title
                # One page.
                pages.append(
                    CrawledPage(
                        url=url, title=title, text=(f"# {title}\n\n" if title else "") + text
                    )
                )
            # Follow links only while depth allows.
            if depth >= options.max_depth:
                # Next address.
                continue
            # Every link on the page...
            for href in collector.links:
                # ...made absolute, without '#fragment'...
                link = urldefrag(urljoin(url, href.strip()))[0]
                # ...web links only, not files like images/PDFs, not seen before.
                if (
                    link.startswith(("http://", "https://"))
                    and not urlsplit(link).path.lower().endswith(_SKIP_SUFFIXES)
                    and link not in seen
                ):
                    # Remember and queue one level deeper.
                    seen.add(link)
                    # Queue it.
                    queue.append((link, depth + 1))
        # Nothing at all could be read (blocked by robots.txt/patterns, or JavaScript-only
        #   pages): a permanent problem, so a clear message instead of retries.
        if not pages:
            # Safe message shown to the tenant.
            raise ValidationError(
                "No readable page was found on this website. Check the address and patterns; "
                "pages that need JavaScript to show text can't be read yet."
            )
        # The pages.
        return pages


# Register under the name 'http'.
@crawler_registry.register("http")
# The factory the registry calls.
def create_http_crawler(http: httpx.AsyncClient) -> HttpCrawler:
    # Settings from CRAWLER_* variables.
    return HttpCrawler(http, CrawlerSettings())

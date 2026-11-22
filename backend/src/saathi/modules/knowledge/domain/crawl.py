# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The settings of one website crawl (P2.4): where to start, how deep to follow links,
#       how many pages at most, and which paths to include or skip.
# Note: This only checks the SHAPE of the settings. The network safety checks (no private
#       addresses etc.) happen in platform/http/url_guard.py before every request.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Crawl options value object. Plain Python (R3)."""

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From typing — type-hint helpers: Any = any type.
from typing import Any

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError

# Follow links at most 3 clicks away from the start page.
MAX_DEPTH = 3
# Never fetch more than 200 pages for one source (bounded job, R33).
MAX_PAGES_LIMIT = 200
# Default page budget.
DEFAULT_MAX_PAGES = 50
# At most 20 include and 20 exclude patterns.
MAX_PATTERNS = 20
# Each pattern at most 200 characters.
MAX_PATTERN_CHARS = 200
# Longest start address.
MAX_URL_CHARS = 2000


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One crawl's settings.
class CrawlOptions:
    # The start page or a sitemap.xml address.
    root_url: str
    # How many link-clicks away from the start page to go (0 = only the start page).
    max_depth: int = 1
    # Page budget.
    max_pages: int = DEFAULT_MAX_PAGES
    # Only paths matching one of these patterns (e.g. '/services/*'); empty = everything.
    include_patterns: tuple[str, ...] = ()
    # Paths matching any of these are skipped (e.g. '/blog/*').
    exclude_patterns: tuple[str, ...] = ()

    # Runs right after __init__: reject invalid values (R20).
    def __post_init__(self) -> None:
        # Only web addresses, bounded length (deep checks happen before fetching).
        if not self.root_url.startswith(("http://", "https://")):
            # 422.
            raise ValidationError("crawl URL must start with http:// or https://")
        # Bounded length.
        if len(self.root_url) > MAX_URL_CHARS:
            # 422.
            raise ValidationError("crawl URL is too long")
        # Depth within range.
        if not 0 <= self.max_depth <= MAX_DEPTH:
            # 422.
            raise ValidationError(f"crawl depth must be between 0 and {MAX_DEPTH}")
        # Page budget within range.
        if not 1 <= self.max_pages <= MAX_PAGES_LIMIT:
            # 422.
            raise ValidationError(f"max pages must be between 1 and {MAX_PAGES_LIMIT}")
        # Check both pattern lists the same way.
        for name, patterns in (
            ("include", self.include_patterns),
            ("exclude", self.exclude_patterns),
        ):
            # Not too many.
            if len(patterns) > MAX_PATTERNS:
                # 422.
                raise ValidationError(f"at most {MAX_PATTERNS} {name} patterns")
            # Each one must be a short, path-like pattern.
            for pattern in patterns:
                # Paths start with '/', and length is bounded.
                if not pattern.startswith("/") or len(pattern) > MAX_PATTERN_CHARS:
                    # 422.
                    raise ValidationError(
                        f"{name} patterns must start with '/' and be at most "
                        f"{MAX_PATTERN_CHARS} characters"
                    )

    # Turn into plain JSON (stored in sources.options).
    def to_json(self) -> dict[str, Any]:
        # One key per field; tuples become lists.
        return {
            "root_url": self.root_url,
            "max_depth": self.max_depth,
            "max_pages": self.max_pages,
            "include_patterns": list(self.include_patterns),
            "exclude_patterns": list(self.exclude_patterns),
        }

    # Build back from stored JSON (validated again by __post_init__).
    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CrawlOptions":
        # Missing optional keys fall back to defaults (older rows keep loading, R22-style).
        return cls(
            root_url=str(data["root_url"]),
            max_depth=int(data.get("max_depth", 1)),
            max_pages=int(data.get("max_pages", DEFAULT_MAX_PAGES)),
            include_patterns=tuple(data.get("include_patterns", ())),
            exclude_patterns=tuple(data.get("exclude_patterns", ())),
        )

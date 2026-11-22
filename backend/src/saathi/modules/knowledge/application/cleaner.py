# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Tidies text before it is cut into chunks (P2.5):
#   1. normalises Unicode and spaces (so the same word always looks the same);
#   2. removes lines that repeat at the top/bottom of most pages (running headers/footers);
#   3. removes page-number lines ('Page 3 of 10', '- 4 -');
#   4. removes common web boilerplate lines ('Skip to content', 'All rights reserved', cookies);
#   5. drops empty pages and exact duplicate pages (the same page crawled twice).
# Rule of thumb: be conservative. Deleting a real sentence is worse than keeping some noise,
#   because the reranker ignores noise but can't bring back a deleted price.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Text cleaning for ingestion (P2.5). Pure functions, no I/O."""

# hashlib — fingerprints (hashes), used to spot duplicate pages.
import hashlib

# re — regular expressions (text patterns).
import re

# unicodedata — Unicode normalisation (NFC).
import unicodedata

# From collections import Counter = counts how often each value appears.
from collections import Counter

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; replace = copy with some fields changed.
from dataclasses import dataclass, replace

# A line that is only a page number: '3', 'Page 3', 'page 3 of 10', '3/10', '- 3 -'.
_PAGE_NUMBER = re.compile(
    r"^[\s\-\u2013\u2014]*(page\s*)?\d{1,4}(\s*(/|of)\s*\d{1,4})?[\s\-\u2013\u2014]*$", re.I
)
# Short web lines that carry no knowledge.
_BOILERPLATE = re.compile(
    r"^(skip to (main )?content|toggle navigation|menu|back to top|share( this)?|"
    # '© 2026 TaxMitra' or 'Copyright 2026 ...' (a year is required, so a real sentence like
    #   'Copyright registration fees are ₹500' is kept).
    r"(©|\(c\)|copyright\s*(©|\(c\))?\s*\d{4}).{0,120}|all rights reserved\.?|"
    r"(this (web)?site|we) uses? cookies.{0,200}|accept( all)? cookies|cookie (policy|settings))$",
    re.I,
)
# Two or more spaces/tabs/no-break spaces inside a line.
_SPACES = re.compile(r"[ \t\u00a0]{2,}")
# Three or more line breaks in a row.
_BLANK_LINES = re.compile(r"\n{3,}")
# Digits, replaced by '#' when comparing headers ('Page 3' and 'Page 4' are the same footer).
_DIGITS = re.compile(r"\d+")
# Look at most this many lines at the top and bottom of each page for headers/footers.
_EDGE_LINES = 2
# A line counts as a running header/footer if it appears on at least 60% of pages...
_REPEAT_SHARE = 0.6
# ...and the document has at least 3 pages (otherwise we can't tell).
_MIN_PAGES_FOR_REPEATS = 3
# Boilerplate patterns only apply to short lines.
_MAX_BOILERPLATE_CHARS = 250


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One page of text on its way to the chunker.
class TextPage:
    # The text ('# Heading' lines mark headings).
    text: str
    # Page number in the file (None for web pages / plain text).
    page: int | None = None
    # The web address (website sources only).
    url: str | None = None
    # The page title (web) or file name.
    title: str = ""


# Normalise one page's characters and spacing.
def normalise_text(text: str) -> str:
    """NFC Unicode, unified line breaks, single spaces, at most one blank line in a row."""
    # NFC joins characters with their accent/vowel marks the same way every time (important for
    #   Hindi/Bengali: the same word can be typed as different code points).
    text = unicodedata.normalize("NFC", text)
    # Windows/old Mac line breaks -> '\n'.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Zero-width spaces and soft hyphens carry no meaning (but keep ZWJ/ZWNJ: Indic scripts need
    #   them to shape conjuncts correctly).
    text = text.replace("​", "").replace("­", "")
    # Collapse runs of spaces inside lines and trim each line.
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    # Join back and allow at most one empty line in a row.
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


# The comparison form of a line (digits ignored, lower case).
def _line_key(line: str) -> str:
    # 'Page 3 - TaxMitra' -> 'page # - taxmitra'.
    return _DIGITS.sub("#", line.strip().lower())


# Find lines that repeat at the edges of most pages.
def _repeated_edge_lines(pages: list[TextPage]) -> set[str]:
    # Too few pages to tell headers from content.
    if len(pages) < _MIN_PAGES_FOR_REPEATS:
        # Nothing to remove.
        return set()
    # How many pages each edge line appears on.
    counts: Counter[str] = Counter()
    # Look at every page...
    for page in pages:
        # ...its non-empty lines...
        lines = [line for line in page.text.split("\n") if line.strip()]
        # ...how many lines at each edge to look at: at most _EDGE_LINES, and never more than a
        #   third of the page, so short pages (slides, web pages) never lose their content.
        edge = min(_EDGE_LINES, (len(lines) - 1) // 3)
        # Too short to have a header/footer.
        if edge <= 0:
            # Next page.
            continue
        # ...the first and last `edge` lines, each counted once per page.
        edges = {_line_key(line) for line in lines[:edge] + lines[-edge:]}
        # Count them.
        counts.update(edges)
    # A line on at least 60% of pages is a running header/footer.
    threshold = max(2, int(len(pages) * _REPEAT_SHARE))
    # Return those (empty keys never count).
    return {key for key, n in counts.items() if key and n >= threshold}


# Is this line noise?
def _is_noise(line: str, repeated: set[str]) -> bool:
    # The trimmed line.
    stripped = line.strip()
    # Empty lines are kept (they separate paragraphs).
    if not stripped:
        # Not noise.
        return False
    # A bare page number.
    if _PAGE_NUMBER.match(stripped):
        # Noise.
        return True
    # A running header/footer.
    if _line_key(stripped) in repeated:
        # Noise.
        return True
    # A short boilerplate line.
    return len(stripped) <= _MAX_BOILERPLATE_CHARS and bool(_BOILERPLATE.match(stripped))


# Clean a whole document (all its pages).
def clean_pages(pages: list[TextPage]) -> list[TextPage]:
    """Normalise, drop headers/footers/page numbers/boilerplate, drop empty and duplicate pages."""
    # Step 1: normalise every page.
    normalised = [replace(p, text=normalise_text(p.text)) for p in pages]
    # Step 2: find running headers/footers across pages.
    repeated = _repeated_edge_lines(normalised)
    # The cleaned pages.
    cleaned: list[TextPage] = []
    # Fingerprints of pages already kept (to drop duplicates).
    seen: set[str] = set()
    # Go through the pages in order...
    for page in normalised:
        # ...remove noise lines...
        kept = [line for line in page.text.split("\n") if not _is_noise(line, repeated)]
        # ...re-tidy blank lines...
        text = _BLANK_LINES.sub("\n\n", "\n".join(kept)).strip()
        # ...skip pages that are now empty...
        if not text:
            # Next page.
            continue
        # ...skip exact duplicates (same text, e.g. '/about' and '/about/' crawled twice)...
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        # Already kept?
        if digest in seen:
            # Next page.
            continue
        # Remember it.
        seen.add(digest)
        # Keep the cleaned page.
        cleaned.append(replace(page, text=text))
    # The clean document.
    return cleaned

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Cuts clean text into chunks (P2.6): passages small enough to search precisely and to
#       fit many into the LLM prompt, big enough to keep their meaning.
# How:
#   1. Read each page line by line. '# Heading' lines (any level) update the 'heading path',
#      e.g. 'Fees > GST filing'. Blank lines separate paragraphs.
#   2. Pack paragraphs into a chunk until the next one would pass the bot's chunk size.
#   3. Start a new chunk at every heading (once the current one has some substance) and at every
#      new web page, so one chunk never mixes two topics or two pages.
#   4. When a chunk is cut because it's full (not at a heading), the next one starts with the
#      last ~15% of the previous one ('overlap'), so a sentence at the boundary is never lost.
#   5. A paragraph too big to sit next to the overlap is split by sentences (., ?, !, ।), and a
#      sentence that is still too big by words.
# Metadata on each chunk: section (heading path), page, url, language.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Heading-aware chunker (P2.6). Pure functions, no I/O."""

# re — regular expressions (text patterns).
import re

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From saathi.modules.knowledge.application.cleaner — page type: TextPage = one page of text.
from saathi.modules.knowledge.application.cleaner import TextPage

# From saathi.modules.knowledge.application.text_metrics — measuring: detect_language = script
#   -> language; estimate_tokens = rough token count.
from saathi.modules.knowledge.application.text_metrics import detect_language, estimate_tokens

# From saathi.modules.knowledge.domain.chunking — chunk rules: Chunk = one passage;
#   ChunkingPolicy = size + overlap.
from saathi.modules.knowledge.domain.chunking import Chunk, ChunkingPolicy

# A markdown heading line: '## Fees'.
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
# Sentence ends: '.', '!', '?', Hindi/Bengali danda '।' and double danda '॥', then space.
_SENTENCE_END = re.compile(r"(?<=[.!?।॥])\s+")
# At a heading, start a new chunk only if the current one has at least this share of the size
#   (otherwise tiny one-line sections would each become a weak chunk of their own).
_MIN_FILL_AT_HEADING = 0.25
# Longest heading path we keep in metadata.
_MAX_SECTION_CHARS = 300


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One paragraph (or heading line) with where it sits.
class _Block:
    # The text.
    text: str
    # Heading path at this point.
    section: str
    # Page number (or None).
    page: int | None
    # Web address (or None).
    url: str | None
    # True for heading lines.
    is_heading: bool
    # Estimated tokens.
    tokens: int


# The heading path text for a set of heading levels: {1: 'Fees', 2: 'GST'} -> 'Fees > GST'.
def _section_path(headings: dict[int, str]) -> str:
    # Levels in order, joined, bounded.
    return " > ".join(headings[k] for k in sorted(headings))[:_MAX_SECTION_CHARS]


# Turn pages into paragraphs/headings, tracking the heading path across pages.
def _blocks(pages: list[TextPage]) -> list[_Block]:
    # The output list.
    blocks: list[_Block] = []
    # The current heading path, one entry per level: {1: 'Fees', 2: 'GST'}.
    headings: dict[int, str] = {}
    # The last web address seen (a new page resets the heading path).
    last_url: str | None = None
    # Go through the pages in order...
    for page in pages:
        # ...a new web page starts with no headings (headings don't carry across sites' pages).
        if page.url != last_url:
            # Reset.
            headings = {}
            # Remember this page.
            last_url = page.url
        # Lines of the current paragraph.
        para: list[str] = []
        # Each line of the page, plus a final empty line that closes the last paragraph...
        for line in [*page.text.split("\n"), ""]:
            # ...trimmed.
            stripped = line.strip()
            # Is it a heading?
            match = _HEADING.match(stripped)
            # A heading or a blank line closes the current paragraph.
            if (match or not stripped) and para:
                # Join its lines with spaces (PDF lines break mid-sentence).
                text = " ".join(para)
                # Add the paragraph block under the current heading path.
                blocks.append(
                    _Block(
                        text,
                        _section_path(headings),
                        page.page,
                        page.url,
                        False,
                        estimate_tokens(text),
                    )
                )
                # Start a fresh paragraph.
                para = []
            # A heading updates the heading path and is kept as text (it gives chunks context).
            if match:
                # Heading level (number of '#') and its text.
                level, title = len(match.group(1)), match.group(2).strip()
                # Forget deeper levels ('## B' after '### A' drops 'A'), then set this level.
                headings = {k: v for k, v in headings.items() if k < level} | {level: title}
                # The heading line itself.
                text = f"{match.group(1)} {title}"
                # Add the heading block.
                blocks.append(
                    _Block(
                        text,
                        _section_path(headings),
                        page.page,
                        page.url,
                        True,
                        estimate_tokens(text),
                    )
                )
            # Normal text belongs to the current paragraph.
            elif stripped:
                # Collect it.
                para.append(stripped)
    # All blocks in order.
    return blocks


# Split text into pieces of at most `limit` tokens (sentences first, then words).
def _split_oversized(text: str, limit: int) -> list[str]:
    # Pieces built so far.
    pieces: list[str] = []
    # The piece being built.
    current: list[str] = []
    # Its size.
    size = 0
    # Units: sentences; a sentence bigger than the limit is broken into words.
    units: list[str] = []
    # Each sentence...
    for sentence in _SENTENCE_END.split(text):
        # ...small enough: keep whole...
        if estimate_tokens(sentence) <= limit:
            # Whole sentence.
            units.append(sentence)
        # ...too big: use its words.
        else:
            # Word by word.
            units.extend(sentence.split())
    # Pack the units...
    for unit in units:
        # ...its size...
        cost = estimate_tokens(unit)
        # ...if it doesn't fit, close the current piece first.
        if current and size + cost > limit:
            # Close it.
            pieces.append(" ".join(current))
            # Start again.
            current, size = [], 0
        # Add the unit.
        current.append(unit)
        # Count it.
        size += cost
    # The last piece.
    if current:
        # Close it.
        pieces.append(" ".join(current))
    # All pieces.
    return pieces


# The last ~`limit` tokens of a text, cut at a sentence or word boundary (for overlap).
def _tail(text: str, limit: int) -> str:
    # No overlap wanted.
    if limit <= 0:
        # Nothing.
        return ""
    # Prefer whole sentences, from the end backwards.
    sentences = _SENTENCE_END.split(text)
    # Collected sentences (reversed order).
    kept: list[str] = []
    # Their size.
    size = 0
    # From the last sentence backwards...
    for sentence in reversed(sentences):
        # ...its size...
        cost = estimate_tokens(sentence)
        # ...stop before passing the limit.
        if size + cost > limit:
            # Stop.
            break
        # Keep it.
        kept.append(sentence)
        # Count it.
        size += cost
    # Got at least one whole sentence: use them.
    if kept:
        # Back in reading order.
        return " ".join(reversed(kept))
    # The last sentence alone is too long: use its last words instead.
    words = sentences[-1].split()
    # Collected words (reversed order).
    tail_words: list[str] = []
    # Their size.
    size = 0
    # From the last word backwards...
    for word in reversed(words):
        # ...its size...
        cost = estimate_tokens(word)
        # ...stop before passing the limit.
        if size + cost > limit:
            # Stop.
            break
        # Keep it.
        tail_words.append(word)
        # Count it.
        size += cost
    # Back in reading order.
    return " ".join(reversed(tail_words))


# Cut cleaned pages into chunks following the bot's policy.
def chunk_pages(pages: list[TextPage], policy: ChunkingPolicy) -> list[Chunk]:
    """Heading-aware packing with overlap. Returns chunks numbered 0, 1, 2..."""
    # The size limit and the overlap budget.
    limit, overlap = policy.chunk_size_tokens, policy.overlap_tokens
    # Finished chunks: (text, section, page, url).
    raw: list[tuple[str, str, int | None, str | None]] = []
    # The chunk being built: its paragraphs (the first may be overlap carried from before)...
    parts: list[str] = []
    # ...its size...
    size = 0
    # ...whether it has content of its own (a chunk holding only carried overlap is not saved)...
    own = False
    # ...where its own content starts (section, page, url of its first block)...
    start: tuple[str, int | None, str | None] = ("", None, None)
    # ...and whether its own content is only headings so far.
    only_headings = False

    # Close the current chunk; `carry` = text repeated at the start of the next one.
    def close(carry: str) -> None:
        # nonlocal: we change the variables of chunk_pages, not new local ones.
        nonlocal parts, size, own
        # Only chunks with their own content are saved.
        if own:
            # Save it.
            raw.append(("\n\n".join(parts), *start))
        # The next chunk starts with the overlap text (if any)...
        parts = [carry] if carry else []
        # ...its size...
        size = estimate_tokens(carry) if carry else 0
        # ...and no content of its own yet.
        own = False

    # Go through the blocks in order...
    for block in _blocks(pages):
        # ...close the current chunk WITHOUT overlap when a new web page starts (never mix
        #   pages) or when a heading starts a new topic and the chunk already has substance.
        new_page = own and block.url != start[2]
        # A heading after enough content.
        new_topic = own and block.is_heading and size >= limit * _MIN_FILL_AT_HEADING
        # Either one closes the chunk.
        if new_page or new_topic:
            # Close without overlap.
            close("")
        # A paragraph that can't fit next to the overlap is split first, into pieces of at most
        #   (size - overlap) tokens, so carried overlap + any piece always fits in one chunk.
        room = limit - overlap
        # Small paragraphs stay whole.
        pieces = _split_oversized(block.text, room) if block.tokens > room else [block.text]
        # Each piece...
        for piece in pieces:
            # ...its size...
            cost = estimate_tokens(piece)
            # ...doesn't fit: close the chunk, carrying its tail as overlap. The overlap is
            #   dropped when overlap + piece would not fit, so no chunk ever passes the limit.
            if own and size + cost > limit:
                # The tail of the chunk being closed.
                carry = _tail("\n\n".join(parts), overlap)
                # Keep the overlap only if it still leaves room for this piece.
                close(carry if estimate_tokens(carry) + cost <= limit else "")
            # First own content of this chunk: remember where it starts.
            if not own:
                # Section/page/url of this block.
                start = (block.section, block.page, block.url)
                # It has content of its own now.
                own = True
                # So far it holds only headings (if this block is one).
                only_headings = block.is_heading
            # A chunk that so far holds only headings ('# Services', '## GST') is labelled with
            #   the deepest heading path, not the first one.
            elif only_headings:
                # Take this block's section.
                start = (block.section, start[1], start[2])
                # Still only headings?
                only_headings = block.is_heading
            # Add the piece.
            parts.append(piece)
            # Count it.
            size += cost
    # Close the last chunk.
    close("")
    # Turn into Chunk objects, numbered in order, dropping any empty text.
    return [
        Chunk(
            index=i,
            text=text,
            section=section,
            page=page,
            url=url,
            language=detect_language(text),
        )
        for i, (text, section, page, url) in enumerate(t for t in raw if t[0].strip())
    ]

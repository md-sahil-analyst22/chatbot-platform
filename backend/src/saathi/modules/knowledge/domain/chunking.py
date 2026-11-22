# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The rules for cutting documents into 'chunks' (small passages the bot searches), and the
#       chunk itself.
# ChunkingPolicy: how big each chunk is (in tokens, roughly 3/4 of a word) and how much
#                 neighbouring chunks overlap. Each bot chooses these in its published config.
# Chunk: one passage + where it came from (source, page, section, language).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Chunking value objects (P2.6). Plain Python: no framework imports (R3)."""

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; field = per-field options.
from dataclasses import dataclass, field

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError

# Smallest allowed chunk (smaller chunks lose context).
MIN_CHUNK_TOKENS = 200
# Largest allowed chunk (bigger chunks dilute relevance and cost more LLM tokens).
MAX_CHUNK_TOKENS = 1200
# Largest allowed overlap (30% of a chunk).
MAX_OVERLAP_RATIO = 0.3
# Plan default (P2.6): 500-800 tokens -> aim for at most 700.
DEFAULT_CHUNK_TOKENS = 700
# Plan default (P2.6): 15% overlap.
DEFAULT_OVERLAP_RATIO = 0.15


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# How to cut documents into chunks.
class ChunkingPolicy:
    # Upper bound of one chunk, in estimated tokens.
    chunk_size_tokens: int = DEFAULT_CHUNK_TOKENS
    # Share of a chunk repeated at the start of the next one (0.15 = 15%).
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO

    # Runs right after __init__: reject invalid values (R20).
    def __post_init__(self) -> None:
        # Size must be within the allowed range.
        if not MIN_CHUNK_TOKENS <= self.chunk_size_tokens <= MAX_CHUNK_TOKENS:
            # 422.
            raise ValidationError(
                f"chunk size must be between {MIN_CHUNK_TOKENS} and {MAX_CHUNK_TOKENS} tokens"
            )
        # Overlap must be within the allowed range.
        if not 0.0 <= self.overlap_ratio <= MAX_OVERLAP_RATIO:
            # 422.
            raise ValidationError(f"chunk overlap must be between 0 and {MAX_OVERLAP_RATIO}")

    # @property: read it like a field.
    @property
    # How many tokens to carry over into the next chunk.
    def overlap_tokens(self) -> int:
        # Size x ratio, rounded down.
        return int(self.chunk_size_tokens * self.overlap_ratio)

    # @property: read it like a field.
    @property
    # A short text that changes whenever the policy changes (part of the source fingerprint).
    def signature(self) -> str:
        # e.g. 'chunk:700:0.150'.
        return f"chunk:{self.chunk_size_tokens}:{self.overlap_ratio:.3f}"


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One searchable passage, before it gets its embedding.
class Chunk:
    # Position in the source (0, 1, 2...).
    index: int
    # The passage text (what the bot reads and cites).
    text: str
    # The heading path it sits under ('Fees > GST filing'), '' if none.
    section: str = ""
    # The page (PDF/sheet number) where it starts, None for web pages and plain text.
    page: int | None = None
    # Detected language code: 'en', 'hi' or 'bn'.
    language: str = "en"
    # The web page address it came from (website sources only).
    url: str | None = None
    # Extra facts kept with the chunk (e.g. sheet name).
    extra: dict[str, str] = field(default_factory=dict)

    # Runs right after __init__: reject invalid values (R20).
    def __post_init__(self) -> None:
        # Positions start at 0.
        if self.index < 0:
            # 422.
            raise ValidationError("chunk index must be >= 0")
        # Empty passages are useless for search.
        if not self.text.strip():
            # 422.
            raise ValidationError("chunk text must not be empty")

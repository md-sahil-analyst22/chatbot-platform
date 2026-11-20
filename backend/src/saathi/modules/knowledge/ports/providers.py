# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contracts for document readers (parsers), embedders and rerankers.
# Plain words: Embedder: turns text into a list of numbers so similar meanings can be found.
#              Reranker: re-orders search results by relevance.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Vendor-neutral ports for ingestion and retrieval.

Object storage is shared with other modules, so its port lives in saathi.platform.storage.
"""

# From collections.abc — standard type names for collections: Sequence = type for a read-only
#   list.
from collections.abc import Sequence

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; field = per-field options such as a default empty list.
from dataclasses import dataclass, field

# From typing — type-hint helpers: Any = any type; Protocol = an interface: any class with these
#   methods fits.
from typing import Any, Protocol


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# Text of one page of a document.
class ParsedPage:
    # Page number.
    number: int
    # The page's text.
    text: str


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# All pages of a parsed document.
class ParsedDocument:
    # All pages in order.
    pages: list[ParsedPage]
    # Extra facts (title, author...), empty by default.
    metadata: dict[str, Any] = field(default_factory=dict)

    # @property: read it like a field (doc.text).
    @property
    # The whole document's text...
    def text(self) -> str:
        # ...pages joined with blank lines.
        return "\n\n".join(p.text for p in self.pages)


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after
#   creation.
@dataclass(frozen=True, slots=True)
# One result after reranking: which document and its score.
class RerankResult:
    # Position of the document in the list that was sent.
    index: int
    # How relevant it is (higher = better).
    score: float


# Contract: file bytes -> text.
class DocumentParser(Protocol):
    # File types this parser understands, e.g. {'.pdf'}.
    supported_extensions: frozenset[str]

    # File bytes + name -> parsed document.
    def parse(self, data: bytes, filename: str) -> ParsedDocument: ...


# Contract: texts -> number vectors.
class Embedder(Protocol):
    # Which model it uses (stored with the vectors).
    model_name: str

    # One vector (list of numbers) per text, in the same order.
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


# Contract: question + documents -> best documents first.
class Reranker(Protocol):
    # Question + documents -> the best `top_n`, best first.
    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int
    ) -> list[RerankResult]: ...

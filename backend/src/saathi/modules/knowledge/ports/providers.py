# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contracts for document readers (parsers), embedders and rerankers.
# Plain words: Embedder: turns text into a list of numbers so similar meanings can be found.
#              Reranker: re-orders search results by relevance.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Vendor-neutral ports for ingestion and retrieval.

Object storage is shared with other modules, so its port lives in saathi.platform.storage.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
# Text of one page of a document.
class ParsedPage:
    number: int
    text: str


@dataclass(frozen=True, slots=True)
# All pages of a parsed document.
class ParsedDocument:
    pages: list[ParsedPage]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


@dataclass(frozen=True, slots=True)
# One result after reranking: which document and its score.
class RerankResult:
    index: int
    score: float


# Contract: file bytes -> text.
class DocumentParser(Protocol):
    supported_extensions: frozenset[str]

    def parse(self, data: bytes, filename: str) -> ParsedDocument: ...


# Contract: texts -> number vectors.
class Embedder(Protocol):
    model_name: str

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


# Contract: question + documents -> best documents first.
class Reranker(Protocol):
    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int
    ) -> list[RerankResult]: ...

"""Vendor-neutral ports for ingestion and retrieval.

Object storage is shared with other modules, so its port lives in saathi.platform.storage.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ParsedPage:
    number: int
    text: str


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    pages: list[ParsedPage]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


@dataclass(frozen=True, slots=True)
class RerankResult:
    index: int
    score: float


class DocumentParser(Protocol):
    supported_extensions: frozenset[str]

    def parse(self, data: bytes, filename: str) -> ParsedDocument: ...


class Embedder(Protocol):
    model_name: str

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int
    ) -> list[RerankResult]: ...

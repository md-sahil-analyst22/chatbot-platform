"""PDF parser adapter (P2.3). Requires the 'ingestion' extra: uv sync --extra ingestion."""

from saathi.modules.knowledge.adapters import parser_registry
from saathi.modules.knowledge.ports.providers import ParsedDocument, ParsedPage


class PyMuPdfParser:
    supported_extensions = frozenset({".pdf"})

    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        import pymupdf  # lazy: only the worker image needs this dependency

        pages: list[ParsedPage] = []
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for i, page in enumerate(doc, start=1):
                pages.append(ParsedPage(number=i, text=page.get_text("text")))
        # Empty text on every page => scanned PDF => OCR fallback (P2.3).
        needs_ocr = all(not p.text.strip() for p in pages)
        return ParsedDocument(pages=pages, metadata={"filename": filename, "needs_ocr": needs_ocr})


@parser_registry.register("pymupdf")
def create_pymupdf_parser() -> PyMuPdfParser:
    return PyMuPdfParser()

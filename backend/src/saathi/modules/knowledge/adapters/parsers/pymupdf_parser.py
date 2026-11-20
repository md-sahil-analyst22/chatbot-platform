# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Reads the text out of PDF files using the PyMuPDF library.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""PDF parser adapter (P2.3). Requires the 'ingestion' extra: uv sync --extra ingestion."""

# From saathi.modules.knowledge.adapters — parser, embedder and reranker registries:
#   parser_registry = document parsers.
from saathi.modules.knowledge.adapters import parser_registry

# From saathi.modules.knowledge.ports.providers — parser, embedder and reranker contracts:
#   ParsedDocument = a parsed document; ParsedPage = one parsed page.
from saathi.modules.knowledge.ports.providers import ParsedDocument, ParsedPage


# The PDF reader.
class PyMuPdfParser:
    # It only reads PDF files.
    supported_extensions = frozenset({".pdf"})

    # PDF bytes -> text per page.
    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        # pymupdf — PyMuPDF, reads PDF files.
        import pymupdf  # lazy: only the worker image needs this dependency

        # The pages we collect.
        pages: list[ParsedPage] = []
        # Open the PDF from memory (closed automatically at the end of the block).
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            # Go through the pages, numbering from 1...
            for i, page in enumerate(doc, start=1):
                # ...and keep each page's plain text.
                pages.append(ParsedPage(number=i, text=page.get_text("text")))
        # Empty text on every page => scanned PDF => OCR fallback (P2.3).
        needs_ocr = all(not p.text.strip() for p in pages)
        # Return the pages plus the file name and the OCR flag.
        return ParsedDocument(pages=pages, metadata={"filename": filename, "needs_ocr": needs_ocr})


# Register under the name 'pymupdf'.
@parser_registry.register("pymupdf")
# The factory the registry calls.
def create_pymupdf_parser() -> PyMuPdfParser:
    # Create the parser (it needs no settings).
    return PyMuPdfParser()

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Reads the text out of PDF files using the PyMuPDF library (P2.3).
# Headings: lines printed noticeably bigger than the page's normal text become '## Heading'
#   lines, so the chunker can cut at section boundaries.
# Scanned PDFs: a page with no text layer is read with OCR (Tesseract, English + Hindi +
#   Bengali) when Tesseract is installed (it is in the worker image). Without it, the page stays
#   empty and ingestion reports "no readable text".
# Limits: at most PDF_MAX_PAGES pages and PDF_OCR_MAX_PAGES OCR pages per file (bounded job, R33).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""PDF parser adapter (P2.3). Requires the 'ingestion' extra: uv sync --extra ingestion."""

# statistics — the median font size of a page.
import statistics

# From typing — type-hint helpers: Any = any type (PyMuPDF's dicts are untyped).
from typing import Any

# structlog — structured logging (JSON log lines).
import structlog

# From pydantic_settings — reads settings from environment variables: BaseSettings = parent
#   class for a settings object; SettingsConfigDict = settings options such as the env prefix.
from pydantic_settings import BaseSettings, SettingsConfigDict

# From saathi.modules.knowledge.adapters — parser, embedder and reranker registries:
#   parser_registry = document parsers.
from saathi.modules.knowledge.adapters import parser_registry

# From saathi.modules.knowledge.ports.providers — parser, embedder and reranker contracts:
#   ParsedDocument = a parsed document; ParsedPage = one parsed page.
from saathi.modules.knowledge.ports.providers import ParsedDocument, ParsedPage

# The logger for this file.
log = structlog.get_logger()

# A line at least this many times the page's median font size is a heading.
_HEADING_RATIO = 1.25
# Headings are short; a long 'big' line is more likely a pull quote or banner.
_MAX_HEADING_CHARS = 120


# Settings read from PDF_* environment variables (R12: the adapter owns its settings).
class PdfParserSettings(BaseSettings):
    # Read PDF_* variables from the environment / .env file.
    model_config = SettingsConfigDict(env_prefix="PDF_", env_file=".env", extra="ignore")

    # Try OCR on pages with no text layer.
    ocr_enabled: bool = True
    # Tesseract languages: English + Hindi + Bengali.
    ocr_languages: str = "eng+hin+ben"
    # Image resolution for OCR (higher = more accurate, slower).
    ocr_dpi: int = 200
    # At most this many pages are OCR'd per file (OCR costs ~1-2 s per page).
    ocr_max_pages: int = 60
    # At most this many pages are read per file.
    max_pages: int = 500


# One page's lines with markdown headings, from PyMuPDF's 'dict' output.
def _page_text_with_headings(page_dict: dict[str, Any]) -> str:
    # (text, biggest font size) for every line.
    lines: list[tuple[str, float]] = []
    # Every text block...
    for block in page_dict.get("blocks", []):
        # ...every line in it...
        for line in block.get("lines", []):
            # ...its spans (runs of same-style text).
            spans = line.get("spans", [])
            # The line's text.
            text = "".join(str(s.get("text", "")) for s in spans).strip()
            # Skip empty lines.
            if not text:
                # Next.
                continue
            # The biggest font size on the line.
            size = max(float(s.get("size", 0.0)) for s in spans)
            # Keep it.
            lines.append((text, size))
        # Block end = paragraph break.
        lines.append(("", 0.0))
    # Font sizes of real text, to find the 'normal' size.
    sizes = [size for text, size in lines if text]
    # No text on the page.
    if not sizes:
        # Empty.
        return ""
    # The page's normal text size.
    body = statistics.median(sizes)
    # Build the output lines.
    out: list[str] = []
    # Each line...
    for text, size in lines:
        # ...a short line printed clearly bigger than normal is a heading...
        if text and size >= body * _HEADING_RATIO and len(text) <= _MAX_HEADING_CHARS:
            # ...written as a markdown heading with blank lines around it.
            out.extend(["", f"## {text}", ""])
        # ...anything else as-is (empty strings keep paragraph breaks).
        else:
            # Keep it.
            out.append(text)
    # Join the lines.
    return "\n".join(out)


# The PDF reader.
class PyMuPdfParser:
    # It only reads PDF files.
    supported_extensions = frozenset({".pdf"})

    # Keep the settings.
    def __init__(self, settings: PdfParserSettings | None = None) -> None:
        # Defaults when none are given (tests).
        self._settings = settings or PdfParserSettings()

    # PDF bytes -> text per page.
    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        # pymupdf — PyMuPDF, reads PDF files.
        import pymupdf  # lazy: only the worker image needs this dependency

        # The settings.
        s = self._settings
        # The pages we collect.
        pages: list[ParsedPage] = []
        # How many pages we OCR'd.
        ocr_pages = 0
        # Whether OCR is (still) usable.
        ocr_available = s.ocr_enabled
        # Open the PDF from memory (closed automatically at the end of the block).
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            # 🔒 Encrypted PDFs can't be read without a password: report no text.
            if doc.needs_pass:
                # Empty document (ingestion reports 'no readable text').
                return ParsedDocument(pages=[], metadata={"filename": filename, "encrypted": True})
            # Go through the pages, numbering from 1, at most max_pages...
            for i, page in enumerate(doc, start=1):
                # ...stop at the page limit.
                if i > s.max_pages:
                    # Stop reading.
                    break
                # Text with headings from the page's text layer.
                text = _page_text_with_headings(page.get_text("dict"))
                # No text layer (scanned page) and OCR allowed: try OCR.
                if not text.strip() and ocr_available and ocr_pages < s.ocr_max_pages:
                    # OCR may fail if Tesseract or a language pack is missing.
                    try:
                        # Render and recognise the whole page.
                        textpage = page.get_textpage_ocr(
                            language=s.ocr_languages, dpi=s.ocr_dpi, full=True
                        )
                        # Plain text from the OCR result.
                        text = page.get_text("text", textpage=textpage)
                        # Count it.
                        ocr_pages += 1
                    # Tesseract missing/broken: stop trying for this file.
                    except Exception as exc:  # OCR is optional; any failure disables it
                        # Log the type only.
                        log.warning("pdf.ocr_unavailable", error_type=type(exc).__name__)
                        # Don't try again on the next pages.
                        ocr_available = False
                # Keep the page.
                pages.append(ParsedPage(number=i, text=text))
        # Empty text on every page => scanned PDF that OCR couldn't read.
        needs_ocr = all(not p.text.strip() for p in pages)
        # Return the pages plus the file name and the OCR facts.
        return ParsedDocument(
            pages=pages,
            metadata={"filename": filename, "needs_ocr": needs_ocr, "ocr_pages": ocr_pages},
        )


# Register under the name 'pymupdf'.
@parser_registry.register("pymupdf")
# The factory the registry calls.
def create_pymupdf_parser() -> PyMuPdfParser:
    # Create the parser with settings from PDF_* variables.
    return PyMuPdfParser(PdfParserSettings())

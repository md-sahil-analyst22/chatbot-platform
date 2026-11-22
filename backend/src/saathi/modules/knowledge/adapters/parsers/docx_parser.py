# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Reads Word (.docx) files with the python-docx library (P2.3).
# Headings: paragraphs styled 'Heading 1'..'Heading 6' (or 'Title') become '#'..'######' lines,
#   so the chunker can cut at section boundaries.
# Tables: each row becomes one line 'Header: value | Header: value', so a price-list row keeps
#   its column names next to its values when it's searched.
# The whole document is one 'page' (Word files have no fixed pages).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""DOCX parser adapter (P2.3). Requires the 'ingestion' extra."""

# io — in-memory files (python-docx reads from a file-like object).
import io

# re — regular expressions (heading style names).
import re

# From typing — type-hint helpers: Any = any type (python-docx objects).
from typing import Any

# From saathi.modules.knowledge.adapters — parser registry: parser_registry = document parsers.
from saathi.modules.knowledge.adapters import parser_registry

# From saathi.modules.knowledge.ports.providers — parser contracts: ParsedDocument = a parsed
#   document; ParsedPage = one parsed page.
from saathi.modules.knowledge.ports.providers import ParsedDocument, ParsedPage

# 'Heading 2' -> level 2.
_HEADING_STYLE = re.compile(r"heading\s*([1-6])", re.I)
# At most this many table rows per table (bounded work for huge tables).
_MAX_TABLE_ROWS = 5000


# Turn one table into 'Header: value | Header: value' lines.
def table_rows_to_text(rows: list[list[str]]) -> list[str]:
    """First row = headers. Rows with no values are skipped. Shared with the spreadsheet parser."""
    # Nothing to do for an empty table.
    if not rows:
        # No lines.
        return []
    # The header row (blank headers get a column number).
    headers = [h.strip() or f"Column {i + 1}" for i, h in enumerate(rows[0])]
    # The output lines.
    lines: list[str] = []
    # Each data row...
    for row in rows[1:]:
        # ...pairs of header and value, skipping empty cells...
        pairs = [
            f"{headers[i] if i < len(headers) else f'Column {i + 1}'}: {cell.strip()}"
            for i, cell in enumerate(row)
            if cell and cell.strip()
        ]
        # ...one line per non-empty row.
        if pairs:
            # Join with ' | '.
            lines.append(" | ".join(pairs))
    # A one-row table has no data rows: keep its cells as plain text instead.
    if not lines and rows[0]:
        # The header cells.
        lines.append(" | ".join(c.strip() for c in rows[0] if c.strip()))
    # The lines.
    return lines


# The heading level of a paragraph's style, or 0.
def _heading_level(paragraph: Any) -> int:
    # The style name ('Heading 2', 'Title', 'Normal'...).
    name = str(getattr(paragraph.style, "name", "") or "")
    # 'Title' is the top level.
    if name.lower() == "title":
        # Level 1.
        return 1
    # 'Heading N'?
    match = _HEADING_STYLE.search(name)
    # Its number, or 0 for normal text.
    return int(match.group(1)) if match else 0


# The Word reader.
class DocxParser:
    # It only reads .docx files.
    supported_extensions = frozenset({".docx"})

    # DOCX bytes -> one page of text with headings and table rows.
    def parse(self, data: bytes, filename: str) -> ParsedDocument:
        # docx — python-docx, reads Word files.
        import docx  # lazy: only the worker image needs this dependency

        # Open the document from memory.
        document = docx.Document(io.BytesIO(data))
        # The output lines.
        lines: list[str] = []
        # Walk the body in order (paragraphs AND tables, as they appear).
        for item in document.iter_inner_content():
            # Paragraphs have .text and .style; tables have .rows.
            if hasattr(item, "rows"):
                # A table: its cells as text, bounded.
                rows = [[cell.text for cell in row.cells] for row in item.rows[:_MAX_TABLE_ROWS]]
                # Blank line, the rows, blank line.
                lines.extend(["", *table_rows_to_text(rows), ""])
                # Next item.
                continue
            # A paragraph's text.
            text = str(item.text).strip()
            # Skip empty paragraphs (but keep a paragraph break).
            if not text:
                # Paragraph break.
                lines.append("")
                # Next item.
                continue
            # Heading level (0 = normal text).
            level = _heading_level(item)
            # Headings become markdown headings with blank lines around them.
            if level:
                # '## Fees'.
                lines.extend(["", f"{'#' * level} {text}", ""])
            # Normal paragraphs are their own paragraph.
            else:
                # Text, then a paragraph break.
                lines.extend([text, ""])
        # One page with all the text.
        return ParsedDocument(
            pages=[ParsedPage(number=1, text="\n".join(lines))], metadata={"filename": filename}
        )


# Register under the name 'docx'.
@parser_registry.register("docx")
# The factory the registry calls.
def create_docx_parser() -> DocxParser:
    # Create the parser (it needs no settings).
    return DocxParser()

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The document parsers (P2.3) on real generated files: PDF headings by font size,
#                Word headings and tables, CSV/Excel row-to-text, plain text, empty/scanned PDFs.
# How to run: cd backend && uv sync --extra ingestion && uv run pytest tests/unit/test_parsers.py
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Parser adapters."""

# io — in-memory files (to build real test documents).
import io

# docx — python-docx, builds a real Word file.
import docx

# openpyxl — builds a real Excel file.
import openpyxl

# pymupdf — PyMuPDF, builds a real PDF.
import pymupdf

# From saathi.modules.knowledge.adapters.parsers.docx_parser — Word parser: DocxParser = reads
#   .docx; table_rows_to_text = rows -> 'Header: value' lines.
from saathi.modules.knowledge.adapters.parsers.docx_parser import DocxParser, table_rows_to_text

# From saathi.modules.knowledge.adapters.parsers.pymupdf_parser — PDF parser: PdfParserSettings
#   = its options (OCR, page limits); PyMuPdfParser = reads PDFs.
from saathi.modules.knowledge.adapters.parsers.pymupdf_parser import (
    PdfParserSettings,
    PyMuPdfParser,
)

# From saathi.modules.knowledge.adapters.parsers.spreadsheet_parser — table parsers: CsvParser,
#   XlsxParser.
from saathi.modules.knowledge.adapters.parsers.spreadsheet_parser import CsvParser, XlsxParser

# From saathi.modules.knowledge.adapters.parsers.text_parser — TextParser = reads TXT/Markdown.
from saathi.modules.knowledge.adapters.parsers.text_parser import TextParser


# PDF lines printed bigger than normal become '##' headings; pages keep their numbers.
def test_pdf_big_lines_become_headings_and_pages_are_numbered() -> None:
    # A new, empty PDF.
    doc = pymupdf.open()
    # Two pages, each...
    for title in ("Fees", "Hours"):
        # ...a new page...
        page = doc.new_page()
        # ...a big title (22 pt)...
        page.insert_text((72, 72), title, fontsize=22)
        # ...and two lines of normal text (10 pt).
        page.insert_text((72, 110), "Body text in normal size goes here.", fontsize=10)
        # Second body line.
        page.insert_text((72, 130), "Another normal line of body text.", fontsize=10)
    # Parse it without OCR.
    parsed = PyMuPdfParser(PdfParserSettings(ocr_enabled=False)).parse(doc.tobytes(), "a.pdf")
    # Pages numbered 1 and 2.
    assert [p.number for p in parsed.pages] == [1, 2]
    # Each title became a markdown heading.
    assert "## Fees" in parsed.pages[0].text and "## Hours" in parsed.pages[1].text
    # The body text is there too.
    assert "Body text in normal size" in parsed.pages[0].text
    # It had text, so no OCR was needed.
    assert parsed.metadata["needs_ocr"] is False


# A page without text (like a scan) is flagged when OCR is off.
def test_pdf_without_text_reports_needs_ocr_when_ocr_is_off() -> None:
    # A PDF...
    doc = pymupdf.open()
    # ...with one blank page.
    doc.new_page()
    # Parse it without OCR.
    parsed = PyMuPdfParser(PdfParserSettings(ocr_enabled=False)).parse(doc.tobytes(), "s.pdf")
    # Flagged as needing OCR...
    assert parsed.metadata["needs_ocr"] is True
    # ...and no text came out.
    assert parsed.text.strip() == ""


# The page limit stops reading huge PDFs (bounded job, R33).
def test_pdf_page_limit_is_enforced() -> None:
    # A PDF...
    doc = pymupdf.open()
    # ...with five pages.
    for _ in range(5):
        # Each says 'x'.
        doc.new_page().insert_text((72, 72), "x")
    # Parse it with a two-page limit.
    parsed = PyMuPdfParser(PdfParserSettings(ocr_enabled=False, max_pages=2)).parse(
        doc.tobytes(), "a.pdf"
    )
    # Only two pages were read.
    assert len(parsed.pages) == 2


# Word headings, paragraphs and tables come out in document order.
def test_docx_headings_paragraphs_and_tables_in_order() -> None:
    # A new Word document.
    d = docx.Document()
    # A level-1 heading.
    d.add_heading("Services", level=1)
    # A paragraph.
    d.add_paragraph("We file GST returns.")
    # A 2x2 table...
    table = d.add_table(rows=2, cols=2)
    # ...header row...
    table.cell(0, 0).text, table.cell(0, 1).text = "Service", "Fee"
    # ...and one data row.
    table.cell(1, 0).text, table.cell(1, 1).text = "GST", "₹500"
    # A level-2 heading.
    d.add_heading("Hours", level=2)
    # Save it into memory.
    buf = io.BytesIO()
    # Save.
    d.save(buf)
    # Parse it.
    text = DocxParser().parse(buf.getvalue(), "a.docx").text
    # Heading, then paragraph, then table row, in that order.
    assert text.index("# Services") < text.index("We file GST") < text.index("Service: GST")
    # The row keeps its column names; the second heading is a '##' heading.
    assert "Service: GST | Fee: ₹500" in text and "## Hours" in text


# Table rows: blank headers get a name, empty cells and rows are skipped.
def test_table_rows_skip_empty_cells_and_name_blank_headers() -> None:
    # Header 'Name' + a blank header; rows: full, empty, half.
    assert table_rows_to_text([["Name", ""], ["A", "1"], ["", ""], ["B", ""]]) == [
        # The blank header became 'Column 2'.
        "Name: A | Column 2: 1",
        # The empty row is gone; the empty cell is skipped.
        "Name: B",
    ]


# CSV rows become 'Header: value' lines; the ';' delimiter is detected.
def test_csv_rows_become_header_value_lines_and_delimiter_is_detected() -> None:
    # Semicolon-separated Bengali table with a byte-order mark at the start.
    data = "﻿সেবা;ফি\nজিএসটি;৫০০\nআয়কর;৮০০\n".encode()
    # Parse it.
    parsed = CsvParser().parse(data, "a.csv")
    # One line per data row, with its column names.
    assert parsed.text.splitlines() == ["সেবা: জিএসটি | ফি: ৫০০", "সেবা: আয়কর | ফি: ৮০০"]


# Each Excel sheet is a page with its name; formulas are never run.
def test_xlsx_sheets_become_pages_with_titles_and_formulas_are_not_evaluated() -> None:
    # A new workbook.
    wb = openpyxl.Workbook()
    # Its first sheet...
    ws = wb.active
    # ...exists.
    assert ws is not None
    # Name it 'Fees'.
    ws.title = "Fees"
    # Header row.
    ws.append(["Service", "Fee"])
    # A data row.
    ws.append(["GST", 500])
    # A formula row (no saved value, so it reads as empty).
    ws.append(["Total", "=SUM(B2:B2)"])
    # A second, empty sheet.
    wb.create_sheet("Empty")
    # Save into memory.
    buf = io.BytesIO()
    # Save.
    wb.save(buf)
    # Parse it.
    parsed = XlsxParser().parse(buf.getvalue(), "a.xlsx")
    # The empty sheet is skipped.
    assert len(parsed.pages) == 1
    # Sheet name as a heading, then the rows; the formula row keeps only 'Total'.
    assert parsed.pages[0].text.splitlines() == [
        "# Fees",
        "",
        "Service: GST | Fee: 500",
        "Service: Total",
    ]


# Markdown is kept as-is and a byte-order mark is dropped.
def test_text_parser_keeps_markdown_and_drops_bom() -> None:
    # A byte-order mark, a heading and a body line.
    parsed = TextParser().parse("﻿# Title\nBody".encode(), "a.md")
    # Same text without the mark.
    assert parsed.text == "# Title\nBody"

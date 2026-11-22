# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: 🔒 Document uploads are judged by their real bytes (R19): renamed files,
#                binary-as-text, zip bombs, oversize files and path tricks in names are refused.
# How to run: cd backend && uv run pytest tests/unit/test_document_uploads.py (no database).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Document upload validation (P2.1)."""

# io — in-memory files (to build real test documents without touching the disk).
import io

# zipfile — builds a zip (for the zip-bomb test).
import zipfile

# docx — python-docx, builds a real Word file.
import docx

# openpyxl — builds a real Excel file.
import openpyxl

# pymupdf — PyMuPDF, builds a real PDF.
import pymupdf

# pytest — the test framework.
import pytest

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError

# From saathi.platform.security.uploads — upload checks: safe_filename = clean a client file
#   name; validate_document = check a document by its bytes.
from saathi.platform.security.uploads import safe_filename, validate_document


# A real one-page PDF.
def _pdf() -> bytes:
    # A new, empty PDF...
    doc = pymupdf.open()
    # ...with one page that says 'Hello'.
    doc.new_page().insert_text((72, 72), "Hello")
    # Its bytes.
    return bytes(doc.tobytes())


# A real .docx.
def _docx() -> bytes:
    # An in-memory file to save into.
    buf = io.BytesIO()
    # A new Word document...
    d = docx.Document()
    # ...with one paragraph.
    d.add_paragraph("Hello")
    # Save it into memory.
    d.save(buf)
    # Its bytes.
    return buf.getvalue()


# A real .xlsx.
def _xlsx() -> bytes:
    # An in-memory file to save into.
    buf = io.BytesIO()
    # A new workbook...
    wb = openpyxl.Workbook()
    # ...with one row in its first sheet.
    wb.active.append(["a", "b"])  # type: ignore[union-attr]  # a new workbook has an active sheet
    # Save it into memory.
    wb.save(buf)
    # Its bytes.
    return buf.getvalue()


# Real documents are recognised by their content.
def test_real_documents_are_accepted_by_content() -> None:
    # A real PDF -> .pdf.
    assert validate_document(_pdf(), "prices.pdf").extension == ".pdf"
    # A real Word file -> .docx.
    assert validate_document(_docx(), "policy.docx").extension == ".docx"
    # A real Excel file -> .xlsx.
    assert validate_document(_xlsx(), "fees.xlsx").extension == ".xlsx"
    # Hindi Markdown (valid UTF-8) -> Markdown.
    assert validate_document("नमस्ते".encode(), "notes.md").content_type == "text/markdown"
    # A CSV with a byte-order mark is still fine.
    assert validate_document(b"\xef\xbb\xbfa,b\n1,2", "t.csv").extension == ".csv"


# Each pair is (bytes, file name) that must be refused.
@pytest.mark.parametrize(
    ("data", "name"),
    [
        (b"", "a.pdf"),  # empty
        (b"%PDF-1.7 ...", "a.txt"),  # a PDF renamed to .txt
        (b"hello", "a.pdf"),  # text renamed to .pdf
        (b"\x00\x01binary", "a.txt"),  # binary pretending to be text
        (b"\xff\xfe\x00bad", "a.csv"),  # not UTF-8
        (b"<svg onload=alert(1)>", "a.svg"),  # unsupported type
        (b"PK\x03\x04not-a-zip", "a.docx"),  # broken zip
    ],
)
# Bad uploads are refused with 422.
def test_bad_uploads_are_refused(data: bytes, name: str) -> None:
    # Expect a validation error...
    with pytest.raises(ValidationError):
        # ...when checking it.
        validate_document(data, name)


# The zip's contents must agree with the extension.
def test_docx_renamed_to_xlsx_is_refused() -> None:
    # A Word file named .xlsx...
    with pytest.raises(ValidationError):
        # ...is refused.
        validate_document(_docx(), "fees.xlsx")


# 🔒 A zip bomb is refused by reading only its table of contents.
def test_zip_bomb_is_refused_before_unpacking() -> None:
    # An in-memory zip...
    buf = io.BytesIO()
    # ...compressed (zeros compress to almost nothing)...
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # ...that looks like an Office file...
        zf.writestr("[Content_Types].xml", "<Types/>")
        # ...but declares 101 MB unpacked.
        zf.writestr("word/document.xml", b"0" * (101 * 1024 * 1024))
    # It is refused with the 'unpacked' message.
    with pytest.raises(ValidationError, match="unpacked"):
        # Check it.
        validate_document(buf.getvalue(), "bomb.docx")


# Files over the size limit are refused.
def test_oversize_file_is_refused() -> None:
    # 11 bytes against a 10-byte limit...
    with pytest.raises(ValidationError, match="at most"):
        # ...is refused.
        validate_document(b"a" * 11, "a.txt", max_bytes=10)


# Each pair is (client file name, safe name we keep).
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Path traversal: only the last part is kept.
        ("../../etc/passwd", "passwd"),
        # Windows path and a space.
        ("C:\\Users\\x\\price list.pdf", "price_list.pdf"),
        # Hidden file: leading dot removed.
        (".hidden.txt", "hidden.txt"),
        # Non-ASCII letters become '_' (the original title is stored separately).
        ("मूल्य.pdf", "_____.pdf"),
        # No name at all.
        ("", "document"),
    ],
)
# 🔒 Client file names never become paths, hidden files or empty names.
def test_safe_filename_strips_paths_and_unsafe_characters(raw: str, expected: str) -> None:
    # The cleaned name is as expected.
    assert safe_filename(raw) == expected


# Long names are shortened but keep their extension.
def test_safe_filename_is_bounded_and_keeps_the_extension() -> None:
    # A 504-character name.
    out = safe_filename("a" * 500 + ".pdf")
    # At most 120 characters, still ending in .pdf.
    assert len(out) <= 120 and out.endswith(".pdf")

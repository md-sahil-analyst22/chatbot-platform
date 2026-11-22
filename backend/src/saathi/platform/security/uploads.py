# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Checks uploaded files by their real content (first bytes), never by their name or
#       claimed type.
# Why: Attackers rename files. SVG is refused because it can contain scripts.
# Also: Documents for the knowledge base (PDF/DOCX/XLSX/CSV/TXT/MD) and zip-bomb limits.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Upload validation by content, never by the client's filename or Content-Type header.

Logos: PNG, JPEG or WebP only. SVG is rejected because it can carry scripts.
Documents (knowledge uploads): PDF, DOCX, XLSX by content; TXT, MD, CSV as strict UTF-8 text.
"""

# io — in-memory files (lets zipfile read bytes without touching the disk).
import io

# zipfile — reads .docx/.xlsx containers (they are zip files inside).
import zipfile

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError

# Logos may be at most 512 KB.
MAX_LOGO_BYTES = 512 * 1024


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# The detected type and file extension.
class ImageInfo:
    # e.g. 'image/png'.
    content_type: str
    # e.g. '.png'.
    extension: str


# Recognise PNG, JPEG or WebP from the file's first bytes.
def sniff_image(data: bytes) -> ImageInfo | None:
    # PNG files always start with these 8 bytes...
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        # ...so it's a PNG.
        return ImageInfo("image/png", ".png")
    # JPEG files start with FF D8 FF...
    if data.startswith(b"\xff\xd8\xff"):
        # ...so it's a JPEG.
        return ImageInfo("image/jpeg", ".jpg")
    # WebP files start with 'RIFF', then 4 size bytes, then 'WEBP'...
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        # ...so it's a WebP.
        return ImageInfo("image/webp", ".webp")
    # Anything else (including SVG) is not accepted.
    return None


# Empty, too big or not an allowed image -> validation error.
def validate_logo(data: bytes, *, max_bytes: int = MAX_LOGO_BYTES) -> ImageInfo:
    # No bytes at all:
    if not data:
        # refuse.
        raise ValidationError("logo file is empty")
    # Bigger than allowed:
    if len(data) > max_bytes:
        # refuse, saying the limit in KB.
        raise ValidationError(f"logo must be at most {max_bytes // 1024} KB")
    # Detect the real type from the first bytes.
    info = sniff_image(data)
    # Not PNG/JPEG/WebP:
    if info is None:
        # refuse.
        raise ValidationError("logo must be a PNG, JPEG or WebP image")
    # Accepted: return the detected type.
    return info


# ───────────────────────────── Documents (knowledge uploads, P2.1) ─────────────────────────────

# Documents may be at most 20 MB (a 30-page PDF is usually 1-5 MB).
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
# 🔒 A .docx/.xlsx may unpack to at most 100 MB in total (zip-bomb guard).
MAX_UNZIPPED_BYTES = 100 * 1024 * 1024
# 🔒 ...and hold at most 5,000 files inside.
MAX_ZIP_ENTRIES = 5000
# Longest file name we keep (after cleaning).
MAX_FILENAME_CHARS = 120

# Plain-text types: their content can't prove which one they are, so the extension decides.
_TEXT_TYPES: dict[str, str] = {
    # Plain text.
    ".txt": "text/plain",
    # Markdown.
    ".md": "text/markdown",
    # Comma-separated table.
    ".csv": "text/csv",
}


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# What a validated document really is.
class DocumentInfo:
    # e.g. 'application/pdf' (decided by the bytes, never by the client).
    content_type: str
    # e.g. '.pdf' (picks the parser).
    extension: str
    # A cleaned, safe file name to show and to use in the storage key.
    safe_name: str


# Turn a client-supplied file name into a short, harmless one.
def safe_filename(filename: str) -> str:
    """Keep letters, digits, '.', '-' and '_' only; never path separators or leading dots."""
    # Drop any folder part a client may send ('../../etc/passwd' -> 'passwd').
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    # Replace every other character with '_' (Hindi/Bengali names become '_', which is fine:
    #   the original title is stored separately and only shown as text).
    cleaned = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "._-") else "_" for ch in base)
    # No leading dots (hidden files) and never empty.
    cleaned = cleaned.lstrip(".") or "document"
    # Bound the length, keeping the extension at the end.
    if len(cleaned) > MAX_FILENAME_CHARS:
        # Split off the extension...
        stem, dot, ext = cleaned.rpartition(".")
        # ...and shorten only the stem.
        cleaned = (
            (stem[: MAX_FILENAME_CHARS - len(ext) - 1] + dot + ext)
            if dot
            else cleaned[:MAX_FILENAME_CHARS]
        )
    # The safe name.
    return cleaned


# The extension of a file name, lower case ('' if none).
def _extension(filename: str) -> str:
    # The part after the last dot, if there is a dot.
    _, dot, ext = filename.rpartition(".")
    # '.pdf' or ''.
    return f".{ext.lower()}" if dot else ""


# Is this zip (docx/xlsx) safe to open, and which Office type is it?
def _sniff_office(data: bytes) -> str | None:
    # Open the zip from memory; a broken zip is simply 'not an Office file'.
    try:
        # Reading the central directory does not unpack anything.
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # The list of files inside.
            infos = zf.infolist()
    # Not a readable zip.
    except (zipfile.BadZipFile, ValueError):
        # Unknown.
        return None
    # 🔒 Too many entries -> refuse (zip-bomb / resource guard).
    if len(infos) > MAX_ZIP_ENTRIES:
        # Raise a clear 422.
        raise ValidationError("document has too many parts")
    # 🔒 The declared unpacked size must stay bounded.
    if sum(i.file_size for i in infos) > MAX_UNZIPPED_BYTES:
        # Raise a clear 422.
        raise ValidationError("document is too large when unpacked")
    # The names inside the zip.
    names = {i.filename for i in infos}
    # Every Office file has this manifest.
    if "[Content_Types].xml" not in names:
        # Some other zip: refuse.
        return None
    # Word documents keep their text here...
    if "word/document.xml" in names:
        # ...so it's a .docx.
        return ".docx"
    # Excel workbooks keep this file...
    if "xl/workbook.xml" in names:
        # ...so it's a .xlsx.
        return ".xlsx"
    # Another Office type (pptx...): not supported.
    return None


# Check an uploaded document by its real bytes and return what it is.
def validate_document(
    data: bytes, filename: str, *, max_bytes: int = MAX_DOCUMENT_BYTES
) -> DocumentInfo:
    """Accept PDF, DOCX, XLSX (by content) and TXT, MD, CSV (valid UTF-8 text, by extension).

    The client's Content-Type header is ignored. A binary file renamed to .txt, or a text file
    renamed to .pdf, is refused.
    """
    # Empty uploads are refused.
    if not data:
        # 422.
        raise ValidationError("file is empty")
    # Too big -> refused.
    if len(data) > max_bytes:
        # 422 with the limit in MB.
        raise ValidationError(f"file must be at most {max_bytes // (1024 * 1024)} MB")
    # The cleaned name and the extension the client claims.
    safe_name, claimed = safe_filename(filename), _extension(filename)
    # PDF files always start with '%PDF-'.
    if data.startswith(b"%PDF-"):
        # The name must agree (a renamed PDF is suspicious and would confuse users).
        if claimed != ".pdf":
            # 422.
            raise ValidationError("file content does not match its extension")
        # A real PDF.
        return DocumentInfo("application/pdf", ".pdf", safe_name)
    # Zip files start with 'PK\x03\x04'.
    if data.startswith(b"PK\x03\x04"):
        # Which Office type, if any (raises on zip bombs).
        office = _sniff_office(data)
        # Unknown zip or mismatched extension -> refuse.
        if office is None or office != claimed:
            # 422.
            raise ValidationError("unsupported file type")
        # The matching content type.
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if office == ".docx"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        # A real Office document.
        return DocumentInfo(content_type, office, safe_name)
    # Everything else must be one of the plain-text types...
    if claimed not in _TEXT_TYPES:
        # ...otherwise refuse.
        raise ValidationError("unsupported file type (pdf, docx, xlsx, csv, txt or md)")
    # 🔒 NUL bytes mean binary content pretending to be text.
    if b"\x00" in data:
        # 422.
        raise ValidationError("file content does not match its extension")
    # Must be valid UTF-8 (a leading BOM is allowed).
    try:
        # Decode strictly: any invalid byte raises.
        data.decode("utf-8-sig")
    # Not UTF-8.
    except UnicodeDecodeError:
        # 422 with a helpful hint.
        raise ValidationError("text files must be UTF-8 encoded") from None
    # A valid text document.
    return DocumentInfo(_TEXT_TYPES[claimed], claimed, safe_name)

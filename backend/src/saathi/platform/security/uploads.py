# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: 🔒 Checks uploaded files by their real content (first bytes), never by their name or
#       claimed type.
# Why: Attackers rename files. SVG is refused because it can contain scripts.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Upload validation by content, never by the client's filename or Content-Type header.

Logos: PNG, JPEG or WebP only. SVG is rejected because it can carry scripts.
"""

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError

# Logos may be at most 512 KB.
MAX_LOGO_BYTES = 512 * 1024


@dataclass(frozen=True, slots=True)
# The detected type and file extension.
class ImageInfo:
    content_type: str
    extension: str


# Recognise PNG, JPEG or WebP from the file's first bytes.
def sniff_image(data: bytes) -> ImageInfo | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ImageInfo("image/png", ".png")
    if data.startswith(b"\xff\xd8\xff"):
        return ImageInfo("image/jpeg", ".jpg")
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ImageInfo("image/webp", ".webp")
    return None


# Empty, too big or not an allowed image -> validation error.
def validate_logo(data: bytes, *, max_bytes: int = MAX_LOGO_BYTES) -> ImageInfo:
    if not data:
        raise ValidationError("logo file is empty")
    if len(data) > max_bytes:
        raise ValidationError(f"logo must be at most {max_bytes // 1024} KB")
    info = sniff_image(data)
    if info is None:
        raise ValidationError("logo must be a PNG, JPEG or WebP image")
    return info

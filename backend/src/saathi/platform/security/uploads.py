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

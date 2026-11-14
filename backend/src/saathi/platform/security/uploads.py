"""Upload validation by content, never by the client's filename or Content-Type header.

Logos: PNG, JPEG or WebP only. SVG is rejected because it can carry scripts.
"""

from dataclasses import dataclass

from saathi.platform.errors import ValidationError

MAX_LOGO_BYTES = 512 * 1024


@dataclass(frozen=True, slots=True)
class ImageInfo:
    content_type: str
    extension: str


def sniff_image(data: bytes) -> ImageInfo | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ImageInfo("image/png", ".png")
    if data.startswith(b"\xff\xd8\xff"):
        return ImageInfo("image/jpeg", ".jpg")
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ImageInfo("image/webp", ".webp")
    return None


def validate_logo(data: bytes, *, max_bytes: int = MAX_LOGO_BYTES) -> ImageInfo:
    if not data:
        raise ValidationError("logo file is empty")
    if len(data) > max_bytes:
        raise ValidationError(f"logo must be at most {max_bytes // 1024} KB")
    info = sniff_image(data)
    if info is None:
        raise ValidationError("logo must be a PNG, JPEG or WebP image")
    return info

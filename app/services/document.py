import base64
from typing import Union

from baml_py import Image, Pdf

from app.config import settings
from app.exceptions import UnsupportedFormatError

# Magic byte signatures for supported file formats.
# We inspect file content directly — never trust client-supplied Content-Type.
_SIGNATURES: list[tuple[bytes, int, str]] = [
    # (magic_bytes, offset, mime_type)
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"%PDF", 0, "application/pdf"),
    (b"II\x2a\x00", 0, "image/tiff"),  # TIFF little-endian
    (b"MM\x00\x2a", 0, "image/tiff"),  # TIFF big-endian
]

SUPPORTED_FORMATS = "PDF, PNG, JPEG, WEBP, TIFF"


def detect_mime_type(content: bytes) -> str | None:
    """Detect MIME type from file magic bytes. Returns None if unrecognized."""
    if len(content) == 0:
        return None

    for magic, offset, mime in _SIGNATURES:
        end = offset + len(magic)
        if len(content) >= end and content[offset:end] == magic:
            return mime

    # WEBP: starts with RIFF....WEBP (bytes 0-3 = RIFF, bytes 8-11 = WEBP)
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"

    return None


def validate_and_convert(
    content: bytes, filename: str
) -> tuple[str, Union[Image, Pdf]]:
    """Validate file content and convert to a BAML-compatible input type.

    Returns (mime_type, baml_input) or raises UnsupportedFormatError.
    """
    if len(content) == 0:
        raise UnsupportedFormatError("Uploaded file is empty")

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise UnsupportedFormatError(
            f"File exceeds maximum size of {settings.max_file_size_mb} MB"
        )

    mime_type = detect_mime_type(content)
    if mime_type is None:
        raise UnsupportedFormatError(
            f"Unsupported file type. Accepted formats: {SUPPORTED_FORMATS}"
        )

    b64 = base64.b64encode(content).decode()

    if mime_type == "application/pdf":
        return mime_type, Pdf.from_base64(b64)
    else:
        return mime_type, Image.from_base64(mime_type, b64)

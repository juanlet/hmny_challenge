import pytest
from baml_py import Image, Pdf

from app.exceptions import UnsupportedFormatError
from app.services.document import detect_mime_type, validate_and_convert
from tests.conftest import MINIMAL_PDF, MINIMAL_PNG


def test_detects_pdf_from_magic_bytes():
    assert detect_mime_type(MINIMAL_PDF) == "application/pdf"


def test_detects_png_from_magic_bytes():
    assert detect_mime_type(MINIMAL_PNG) == "image/png"


def test_detects_jpeg_from_magic_bytes():
    jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    assert detect_mime_type(jpeg_header) == "image/jpeg"


def test_rejects_unknown_magic_bytes():
    with pytest.raises(UnsupportedFormatError):
        validate_and_convert(b"not a real file", "mystery.bin")


def test_rejects_empty_content():
    with pytest.raises(UnsupportedFormatError, match="empty"):
        validate_and_convert(b"", "empty.png")


def test_rejects_oversized_file():
    from app.config import settings

    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (settings.max_file_size_mb * 1024 * 1024 + 1)
    with pytest.raises(UnsupportedFormatError, match="size"):
        validate_and_convert(oversized, "huge.png")


def test_pdf_returns_pdf_baml_type():
    mime, baml_input = validate_and_convert(MINIMAL_PDF, "doc.pdf")
    assert mime == "application/pdf"
    assert isinstance(baml_input, Pdf)


def test_image_returns_image_baml_type():
    mime, baml_input = validate_and_convert(MINIMAL_PNG, "photo.png")
    assert mime == "image/png"
    assert isinstance(baml_input, Image)

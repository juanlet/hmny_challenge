from unittest.mock import AsyncMock, patch

import pytest
from baml_py.baml_py import BamlClientError

from tests.conftest import MINIMAL_PDF, MINIMAL_PNG

PATCH_TARGET = "app.services.extraction.b.ExtractIncome"


@patch(PATCH_TARGET, new_callable=AsyncMock)
async def test_happy_path_image(mock_extract, client, mock_baml_success, minimal_png_bytes):
    mock_extract.return_value = mock_baml_success
    resp = await client.post(
        "/submissions",
        files={"file": ("pay_stub.png", minimal_png_bytes, "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["employer_name"] == "Acme Corp"
    assert body["data"]["gross_income"] == 5000.0
    assert body["errors"] == []


@patch(PATCH_TARGET, new_callable=AsyncMock)
async def test_happy_path_pdf(mock_extract, client, mock_baml_success, minimal_pdf_bytes):
    mock_extract.return_value = mock_baml_success
    resp = await client.post(
        "/submissions",
        files={"file": ("statement.pdf", minimal_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@patch(PATCH_TARGET, new_callable=AsyncMock)
async def test_missing_required_fields(mock_extract, client, mock_baml_missing_fields, minimal_png_bytes):
    mock_extract.return_value = mock_baml_missing_fields
    resp = await client.post(
        "/submissions",
        files={"file": ("doc.png", minimal_png_bytes, "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "partial"
    error_fields = {e["field"] for e in body["errors"]}
    assert "employer_name" in error_fields
    assert "gross_income" in error_fields
    assert all(e["error_type"] == "missing_field" for e in body["errors"])


@patch(PATCH_TARGET, new_callable=AsyncMock)
async def test_baml_parse_error(mock_extract, client, minimal_png_bytes):
    mock_extract.side_effect = BamlClientError("LLM returned unparseable output")
    resp = await client.post(
        "/submissions",
        files={"file": ("doc.png", minimal_png_bytes, "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert body["errors"][0]["error_type"] == "extraction_failed"


async def test_unsupported_format_txt(client):
    resp = await client.post(
        "/submissions",
        files={"file": ("readme.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["error_type"] == "unsupported_format"


async def test_unsupported_format_spoofed_extension(client):
    resp = await client.post(
        "/submissions",
        files={"file": ("doc.pdf", b"this is not a pdf", "application/pdf")},
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["error_type"] == "unsupported_format"


async def test_empty_file(client):
    resp = await client.post(
        "/submissions",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["error_type"] == "unsupported_format"


async def test_no_file_uploaded(client):
    resp = await client.post("/submissions")
    assert resp.status_code == 422

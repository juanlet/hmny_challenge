import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from baml_client.types import DocumentType
from baml_py.baml_py import BamlClientError

from tests.conftest import MINIMAL_PDF, MINIMAL_PNG

PATCH_TARGET = "app.services.graph.b.ExtractIncome"
CLASSIFY_TARGET = "app.services.graph.b.ClassifyDocument"


async def _poll_until_done(client, job_id: str, max_polls: int = 30):
    """Poll GET /submissions/{job_id} until it reaches a terminal status."""
    for _ in range(max_polls):
        resp = await client.get(f"/submissions/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in ("completed", "failed"):
            return body
        await asyncio.sleep(0.05)
    raise TimeoutError("Job did not complete in time")


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_happy_path_image(mock_classify, mock_extract, client, mock_baml_success, minimal_png_bytes):
    mock_classify.return_value = DocumentType.Income
    mock_extract.return_value = mock_baml_success
    resp = await client.post(
        "/submissions",
        files={"file": ("pay_stub.png", minimal_png_bytes, "image/png")},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    job = await _poll_until_done(client, job_id)
    assert job["status"] == "completed"
    result = job["result"]
    assert result["status"] == "success"
    assert result["data"]["employer_name"] == "Acme Corp"
    assert result["data"]["gross_income"] == 5000.0
    assert result["errors"] == []


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_happy_path_pdf(mock_classify, mock_extract, client, mock_baml_success, minimal_pdf_bytes):
    mock_classify.return_value = DocumentType.Income
    mock_extract.return_value = mock_baml_success
    resp = await client.post(
        "/submissions",
        files={"file": ("statement.pdf", minimal_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 202
    job = await _poll_until_done(client, resp.json()["job_id"])
    assert job["result"]["status"] == "success"


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_missing_required_fields(mock_classify, mock_extract, client, mock_baml_missing_fields, minimal_png_bytes):
    mock_classify.return_value = DocumentType.Income
    mock_extract.return_value = mock_baml_missing_fields
    resp = await client.post(
        "/submissions",
        files={"file": ("doc.png", minimal_png_bytes, "image/png")},
    )
    assert resp.status_code == 202
    job = await _poll_until_done(client, resp.json()["job_id"])
    result = job["result"]
    assert result["status"] == "partial"
    error_fields = {e["field"] for e in result["errors"]}
    assert "employer_name" in error_fields
    assert "gross_income" in error_fields
    assert all(e["error_type"] == "missing_field" for e in result["errors"])


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_baml_parse_error(mock_classify, mock_extract, client, minimal_png_bytes):
    mock_classify.return_value = DocumentType.Income
    mock_extract.side_effect = BamlClientError("LLM returned unparseable output")
    resp = await client.post(
        "/submissions",
        files={"file": ("doc.png", minimal_png_bytes, "image/png")},
    )
    assert resp.status_code == 202
    job = await _poll_until_done(client, resp.json()["job_id"])
    result = job["result"]
    assert result["status"] == "error"
    assert result["data"] is None
    assert result["errors"][0]["error_type"] == "extraction_failed"


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


async def test_get_nonexistent_job(client):
    resp = await client.get("/submissions/nonexistent123")
    assert resp.status_code == 404

# Tests ✅

## Overview

Write unit and integration tests covering the full behavioral surface of the API — with emphasis on the three required failure cases. Tests must run with `pytest` using mocked LLM responses; no API keys or network access should be required. The testing philosophy here is behavioral coverage over line coverage: each test exercises a meaningful scenario that could fail in production.

## Requirements

### `tests/conftest.py` — shared fixtures

- `client` fixture — `TestClient` wrapping the FastAPI app (sync); use `httpx` for async if needed
- `minimal_png_bytes` fixture — a valid 1×1 pixel PNG as raw bytes (hardcode the known PNG magic bytes + minimal valid PNG structure so no image library is needed)
- `minimal_pdf_bytes` fixture — a minimal valid PDF header (`%PDF-1.4\n%%EOF\n`) as bytes
- `mock_baml_success` fixture factory — returns a mock `IncomeExtraction` object with all required fields populated:
  ```python
  IncomeExtraction(
      employer_name="Acme Corp",
      employee_name="Jane Doe",
      gross_income=5000.0,
      net_income=3800.0,
      pay_frequency=PayFrequency.BiWeekly,
      income_period=IncomePeriod(start_date="2024-01-01", end_date="2024-01-14"),
      document_type="pay_stub",
      currency="USD",
      confidence_notes=[],
  )
  ```
- `mock_baml_missing_fields` fixture — same as above but `employer_name=None` and `gross_income=None`

### `tests/test_submissions.py` — API integration tests

Use `unittest.mock.patch` to mock `app.services.extraction.b.ExtractIncome`.

| Test | Mock behavior | Expected response |
|---|---|---|
| `test_happy_path_image` | Returns full `IncomeExtraction` | HTTP 200, `status="success"`, `data.employer_name="Acme Corp"`, `errors=[]` |
| `test_happy_path_pdf` | Returns full `IncomeExtraction` | HTTP 200, `status="success"` |
| `test_missing_required_fields` | Returns `IncomeExtraction` with `employer_name=None`, `gross_income=None` | HTTP 200, `status="partial"`, `errors` contains two `missing_field` entries for those fields |
| `test_baml_parse_error` | Raises `BamlClientError("LLM returned unparseable output")` | HTTP 200, `status="error"`, `errors[0].error_type="extraction_failed"` |
| `test_unsupported_format_txt` | No mock needed — never reaches BAML | HTTP 422, `errors[0].error_type="unsupported_format"` |
| `test_unsupported_format_spoofed_extension` | Upload a text file with `filename="doc.pdf"` | HTTP 422, `errors[0].error_type="unsupported_format"` (magic bytes check catches it) |
| `test_empty_file` | No mock needed | HTTP 422, `errors[0].error_type="unsupported_format"` |
| `test_no_file_uploaded` | No mock needed | HTTP 422 (FastAPI validation) |

### `tests/test_extraction.py` — unit tests for extraction service

Test `extract_from_document` directly, bypassing the HTTP layer.

- `test_returns_success_when_all_fields_present` — mock `b.ExtractIncome` to return full data; assert `status="success"` and `errors=[]`
- `test_returns_partial_when_pay_frequency_missing` — mock returns `pay_frequency=None`; assert `status="partial"` and exactly one `missing_field` error for `pay_frequency`
- `test_returns_error_on_baml_exception` — mock raises; assert `status="error"`, `data=None`
- `test_negative_gross_income_is_validation_error` — mock returns `gross_income=-100.0`; assert `status="partial"`, error has `error_type="validation_error"` and `field="gross_income"`
- `test_processing_time_is_populated` — assert `metadata["processing_time_ms"]` is a positive number

### `tests/test_document.py` — unit tests for document validation

Test `validate_and_convert` and `detect_mime_type` directly.

- `test_detects_pdf_from_magic_bytes`
- `test_detects_png_from_magic_bytes`
- `test_detects_jpeg_from_magic_bytes`
- `test_rejects_unknown_magic_bytes` — assert raises `UnsupportedFormatError`
- `test_rejects_empty_content` — assert raises `UnsupportedFormatError`
- `test_rejects_oversized_file` — create bytes larger than `max_file_size_mb`; assert raises `UnsupportedFormatError` with size message
- `test_pdf_returns_pdf_baml_type` — assert returned BAML input is `Pdf` instance
- `test_image_returns_image_baml_type` — assert returned BAML input is `Image` instance

## CRITICAL: Mocking BAML's async client

BAML's async client (`b.ExtractIncome`) is an async method. Use `AsyncMock`:

```python
from unittest.mock import AsyncMock, patch

@patch("app.services.extraction.b.ExtractIncome", new_callable=AsyncMock)
async def test_happy_path(mock_extract, client, mock_baml_success):
    mock_extract.return_value = mock_baml_success
    response = client.post("/submissions", files={"file": ("pay_stub.png", minimal_png_bytes, "image/png")})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
```

Patching `app.services.extraction.b.ExtractIncome` (the import path *within the module under test*) is correct — do not patch the BAML library itself.

## Notes

- The `BamlClientError` import path is `baml_py.BamlClientError` — verify during implementation
- Test fixture `minimal_png_bytes` can be hardcoded as:
  ```python
  # Valid 1x1 transparent PNG (68 bytes)
  MINIMAL_PNG = bytes.fromhex(
      "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
      "890000000a49444154789c6260000000020001e221bc330000000049454e44ae426082"
  )
  ```
- If `pytest-asyncio` is configured with `asyncio_mode = "auto"`, no `@pytest.mark.asyncio` decorators are needed on async tests

# API Endpoint & Error Handling

## Overview

Wire the document validation and extraction service into the `POST /submissions` FastAPI endpoint. This phase also completes the global exception handler setup in `app/main.py` so that every failure mode — whether from an unsupported file, an LLM error, or an unexpected exception — returns a consistent, structured JSON response. The API contract must never leak a raw 500 with a traceback.

## Requirements

### `POST /submissions` — `app/api/submissions.py`

- Accept `file: UploadFile = File(...)` as a multipart form field
- Read file contents with `content = await file.read()`
- Call `extract_from_document(content, file.filename or "")` from the extraction service
- Return the `SubmissionResponse` directly with status code `200` on all extraction outcomes — including `"partial"` and `"error"` statuses, since these are structured business responses, not HTTP failures
- The only HTTP 4xx/5xx responses come from the global exception handlers (see below)

### `GET /health` — `app/main.py`

- Returns `{"status": "ok"}` with HTTP 200
- No auth, no dependencies — used by Docker health checks and load balancers

### Global exception handlers — `app/main.py`

All handlers must return a JSON body matching this shape for consistency:

```json
{
  "status": "error",
  "data": null,
  "errors": [
    {
      "field": null,
      "error_type": "unsupported_format",
      "message": "Unsupported file type. Accepted formats: PDF, PNG, JPEG, WEBP, TIFF",
      "raw_value": null
    }
  ],
  "metadata": {}
}
```

| Exception | HTTP Status | `error_type` |
|---|---|---|
| `UnsupportedFormatError` | 422 | `"unsupported_format"` |
| `ExtractionError` | 422 | `"extraction_failed"` |
| `DocumentProcessingError` | 502 | `"extraction_failed"` |
| `RequestValidationError` (FastAPI) | 422 | `"validation_error"` |
| `Exception` (catch-all) | 500 | `"extraction_failed"` — message must be generic, never expose internal details |

Register handlers using `@app.exception_handler(ExceptionClass)` in `main.py`.

### Router registration

```python
from app.api import submissions
app.include_router(submissions.router, prefix="", tags=["submissions"])
```

## Notes

- Using HTTP 200 for `"partial"` and `"error"` extraction statuses is intentional: these document-level outcomes are part of the API's normal business response, not HTTP failures. The caller should check the `status` field to determine how to proceed. This is a common pattern in document processing APIs.
- The catch-all `Exception` handler should log the full traceback internally (via `structlog`) but only return a generic message to the caller — never expose stack traces or internal error details in responses (OWASP: Security Misconfiguration / Information Disclosure)
- `file.filename` may be `None` if the client does not send a filename; default to `""` to avoid a `None` propagating into the service layer
- Do not add request body size limits in the endpoint itself — FastAPI/uvicorn have their own limits, and the file size check in `validate_and_convert` handles the business-level limit

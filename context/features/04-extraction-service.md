# Extraction Service & Response Models

## Overview

Implement the core orchestration logic that calls BAML, post-validates the LLM's output against business rules, and assembles a structured `SubmissionResponse`. This is the heart of the application — it must handle *all three required failure cases* with actionable, consistent error shapes. The response model design must allow callers to determine exactly what succeeded, what failed, and why, without parsing error message strings.

## Requirements

### Response models — `app/schemas/responses.py`

- `ErrorType` — `Literal["missing_field", "validation_error", "unsupported_format", "extraction_failed"]`
- `ErrorDetail(BaseModel)`:
  - `field: str | None` — name of the field that failed, or `None` for document-level errors
  - `error_type: ErrorType`
  - `message: str` — human-readable explanation
  - `raw_value: str | None = None` — the raw string the LLM returned before validation (for `validation_error` cases)
- `IncomePeriodData(BaseModel)` — `start_date: str`, `end_date: str`
- `ExtractionData(BaseModel)` — mirrors `IncomeExtraction` from BAML but with required fields typed as non-optional (populated only when status is `"success"` or `"partial"`):
  - `employer_name: str | None`
  - `employee_name: str | None`
  - `gross_income: float | None`
  - `net_income: float | None`
  - `pay_frequency: str | None`
  - `income_period: IncomePeriodData | None`
  - `document_type: str | None`
  - `currency: str | None`
  - `confidence_notes: list[str]`
- `SubmissionResponse(BaseModel)`:
  - `status: Literal["success", "partial", "error"]`
  - `data: ExtractionData | None` — present on `"success"` and `"partial"`, `None` on `"error"`
  - `errors: list[ErrorDetail]` — empty on `"success"`, populated on `"partial"` and `"error"`
  - `metadata: dict[str, str | int | float]` — `model_used`, `processing_time_ms`

### Status semantics

| Status | Meaning |
|---|---|
| `"success"` | All required fields (`employer_name`, `gross_income`, `pay_frequency`) extracted and valid |
| `"partial"` | BAML parsed the LLM response, but ≥1 required field is `None`; `data` contains whatever was extracted |
| `"error"` | BAML could not parse the LLM response at all, or the document processing layer failed; `data` is `None` |

### Extraction service — `app/services/extraction.py`

- `async def extract_from_document(content: bytes, filename: str) -> SubmissionResponse`
- Flow:
  1. Record `start_time = time.monotonic()`
  2. Call `validate_and_convert(content, filename)` → `(mime_type, baml_input)`; `UnsupportedFormatError` propagates up to the endpoint
  3. Call `await b.ExtractIncome(doc=baml_input)` inside a `try/except`
  4. On `BamlClientError` or any BAML exception → return `SubmissionResponse(status="error", data=None, errors=[ErrorDetail(field=None, error_type="extraction_failed", message=str(e))], metadata=...)`
  5. Post-validate the returned `IncomeExtraction` object — collect `ErrorDetail` entries for each required field that is `None`
  6. If `errors` is empty → `status="success"`; if `errors` is non-empty → `status="partial"`
  7. Populate `metadata` with `model_used` (from BAML result or config) and `processing_time_ms`

### Required field validation (Failure Case #1)

```python
REQUIRED_FIELDS = ["employer_name", "gross_income", "pay_frequency"]

for field in REQUIRED_FIELDS:
    if getattr(result, field) is None:
        errors.append(ErrorDetail(
            field=field,
            error_type="missing_field",
            message=f"'{field}' could not be extracted from the document",
        ))
```

### Schema validation error handling (Failure Case #2)

BAML's parser handles most type coercion failures internally. However, the BAML `IncomeExtraction` schema uses `float?` for `gross_income`, which means BAML will return `None` (not raise) if the LLM returns a non-numeric string. This maps naturally to Failure Case #1 (missing field). Test this case by mocking `b.ExtractIncome` to raise a `BamlClientError`, simulating a total parse failure where no structured data can be recovered.

For an explicit validation error scenario (e.g. LLM returns `gross_income = -500`), add a post-validation check:

```python
if result.gross_income is not None and result.gross_income <= 0:
    errors.append(ErrorDetail(
        field="gross_income",
        error_type="validation_error",
        message="gross_income must be a positive number",
        raw_value=str(result.gross_income),
    ))
```

## Notes

- Import `b` from `baml_client.async_client` so the extraction service is fully async and compatible with FastAPI's async request handlers
- The service layer never raises HTTP exceptions — it returns `SubmissionResponse` on all paths except `UnsupportedFormatError` (which propagates intentionally for the endpoint to handle via global exception handler)
- `metadata.model_used` should reflect which model actually responded (primary vs. fallback); read this from `b.ExtractIncome`'s return context if BAML exposes it, otherwise default to the configured primary model name

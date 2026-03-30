# Harmony Document Extraction API

A backend service that accepts uploaded income documents, uses an LLM to extract structured data, and returns clean, validated output with actionable error reporting.

## Quick Start

```bash
cp .env.example .env          # add your OpenAI and/or Anthropic API keys
docker-compose up --build      # starts on http://localhost:8000
```

**Without Docker:**

```bash
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
baml-cli generate
uvicorn app.main:app --reload
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/ui/` | Web UI for document upload and extraction |
| `POST` | `/submissions` | Upload a document and extract income data (API) |
| `GET` | `/health` | Health check |

### Example: Upload a Document

```bash
curl -X POST http://localhost:8000/submissions \
  -F "file=@/path/to/pay_stub.pdf"
```

### Response Shape

**Success** — all required fields extracted:

```json
{
  "status": "success",
  "data": {
    "employer_name": "Acme Corp",
    "employee_name": "Jane Doe",
    "gross_income": 5000.00,
    "net_income": 3800.00,
    "pay_frequency": "BiWeekly",
    "income_period": { "start_date": "2024-01-01", "end_date": "2024-01-14" },
    "document_type": "pay_stub",
    "currency": "USD",
    "confidence_notes": []
  },
  "errors": [],
  "metadata": { "model_used": "GPT4o", "processing_time_ms": 2340 }
}
```

**Partial** — some required fields could not be extracted:

```json
{
  "status": "partial",
  "data": {
    "employer_name": null,
    "gross_income": null,
    "pay_frequency": "Monthly",
    "confidence_notes": ["employer name not clearly visible"]
  },
  "errors": [
    { "field": "employer_name", "error_type": "missing_field", "message": "'employer_name' could not be extracted from the document" },
    { "field": "gross_income", "error_type": "missing_field", "message": "'gross_income' could not be extracted from the document" }
  ],
  "metadata": { "model_used": "GPT4o", "processing_time_ms": 1820 }
}
```

**Error** — unsupported file format:

```json
{
  "status": "error",
  "data": null,
  "errors": [
    { "field": null, "error_type": "unsupported_format", "message": "Unsupported file type. Accepted formats: PDF, PNG, JPEG, WEBP, TIFF" }
  ],
  "metadata": {}
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `GOOGLE_API_KEY` | — | Google AI (Gemini) API key |
| `XAI_API_KEY` | — | xAI (Grok) API key |
| `LLM_PRIMARY_PROVIDER` | `openai` | Primary LLM provider (`openai`, `anthropic`, `google`, or `xai`). Falls back through the chain on failure. |
| `MAX_FILE_SIZE_MB` | `10` | Maximum upload file size in megabytes |

## Running Tests

```bash
pytest -v
```

All 21 tests use mocked LLM responses — **no API keys required**.

## Architecture

```
POST /submissions
     │
     ▼
 document.py ──► magic byte validation ──► BAML Image / Pdf
     │
     ▼
 extraction.py ──► b.ExtractIncome(doc) ──► LLM (GPT-4o → Claude → Gemini → Grok)
     │
     ▼
 post-validation ──► SubmissionResponse (success / partial / error)
```

The API validates uploaded files by inspecting magic bytes (never trusting `Content-Type`), converts them to BAML's native `Image` or `Pdf` types, and passes them to an LLM extraction function. BAML handles structured output parsing, type coercion, and provider fallback. A post-validation layer checks for missing required fields and business-rule violations, producing a three-state response: `success`, `partial`, or `error`. Structured JSON logging (via structlog) and a request-scoped `request_id` provide observability.



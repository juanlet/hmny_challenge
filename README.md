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
| `GET` | `/` | Web UI for document upload and extraction |
| `POST` | `/submissions` | Upload a document — returns a job ID (202) |
| `GET` | `/submissions/{job_id}` | Poll extraction job status and result |
| `GET` | `/health` | Health check |

### Example: Upload a Document

```bash
# Submit a document — returns a job ID
curl -X POST http://localhost:8000/submissions \
  -F "file=@/path/to/pay_stub.pdf"
# {"job_id": "a1b2c3d4e5f6", "status": "processing"}

# Poll for the result
curl http://localhost:8000/submissions/a1b2c3d4e5f6
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
| `LLM_PRIMARY_PROVIDER` | `auto` | Primary LLM provider (`openai`, `anthropic`, `google`, `xai`, or `auto`). `auto` selects the first provider whose API key is set. |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model name |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic model name |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Google Gemini model name |
| `XAI_MODEL` | `grok-3` | xAI Grok model name |
| `MAX_FILE_SIZE_MB` | `10` | Maximum upload file size in megabytes |

## Running Tests

```bash
pytest -v
```

All 22 tests use mocked LLM responses — **no API keys required**.

## Architecture

```
POST /submissions
     │
     ▼
 validate format (magic bytes)  →  422 if unsupported
     │
     ▼
 create job → return 202 {job_id}
     │                     ▲
     ▼ (background)        │  GET /submissions/{job_id}
 ┌───────────────────────┐ │
 │  LangGraph Pipeline   │ │
 │                       │ │
 │  validate_document    │ │
 │       ↓               │ │
 │  extract_via_llm      │ │
 │  (BAML → LLM)         │ │
 │       ↓               │ │
 │  post_validate        │ │
 └───────────────────────┘ │
     │                     │
     ▼                     │
  store result ────────────┘
```

The API validates uploaded files by inspecting magic bytes (never trusting `Content-Type`), then immediately returns a job ID. A LangGraph `StateGraph` pipeline runs the extraction in the background through three nodes: document validation, BAML-powered LLM extraction (with a 4-provider fallback chain: GPT-4o → Claude → Gemini → Grok), and post-validation of required fields and business rules. Clients poll `GET /submissions/{job_id}` for results. The web UI at `/` does this polling automatically with a progress indicator.



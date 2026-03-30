# Bonus Features

## Overview

Implement three production-readiness signals that elevate the project above a basic take-home: structured JSON logging, Docker Compose setup, and a configurable runtime LLM fallback chain. These are treated as a single focused phase because they are each small, independent, and build directly on what already exists — no structural changes to the core extraction pipeline.

## Requirements

### Structured logging — `structlog`

- Configure `structlog` in `app/main.py` at import time (before the app is created):
  ```python
  import structlog
  structlog.configure(
      processors=[
          structlog.processors.TimeStamper(fmt="iso"),
          structlog.processors.add_log_level,
          structlog.processors.JSONRenderer(),
      ]
  )
  ```
- Add a request-scoped middleware that generates a UUID `request_id` per request and binds it to the structlog context via `structlog.contextvars.bind_contextvars(request_id=...)`; clear context vars after response with `structlog.contextvars.clear_contextvars()`
- Log the following events with appropriate fields:
  | Location | Event | Fields |
  |---|---|---|
  | `POST /submissions` entry | `"document_received"` | `filename`, `content_length` |
  | After `validate_and_convert` | `"document_validated"` | `mime_type` |
  | After `b.ExtractIncome` success | `"extraction_complete"` | `status`, `missing_fields` (list of field names) |
  | On BAML exception | `"extraction_failed"` | `error` (str) |
  | On `UnsupportedFormatError` | `"unsupported_format"` | `detail` |
  | Catch-all exception handler | `"unexpected_error"` | `error` (generic message, no traceback in log line) |
- Use `logger = structlog.get_logger()` at module level; do not use Python's `logging` module directly

### Docker Compose

- `Dockerfile` — multi-stage build:
  - Stage 1 `builder`: `python:3.12-slim`, install deps into `/install` via `pip install --prefix=/install`
  - Stage 2 `runtime`: `python:3.12-slim`, copy from `/install`, copy `app/` and `baml_client/` (generated at build time), set `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
  - Run `baml-cli generate` as part of the `builder` stage so `baml_client/` is baked in and the runtime image needs no `baml-py` dev tooling
- `docker-compose.yml`:
  ```yaml
  services:
    api:
      build: .
      ports:
        - "8000:8000"
      env_file:
        - .env
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
        interval: 10s
        timeout: 5s
        retries: 3
  ```
- Document in README that `docker-compose up --build` is the zero-config startup path

### Runtime LLM fallback chain

The BAML `ExtractorWithFallback` client (defined in Phase 2) already handles provider fallback transparently. This bonus extends that by making the *primary* provider selectable at runtime via environment variable, enabling easy switching without code changes:

- Add `LLM_PRIMARY_PROVIDER: str = "openai"` to `Settings` in `app/config.py`; accepted values: `"openai"`, `"anthropic"`
- In `app/services/extraction.py`, before calling `b.ExtractIncome`, build a `ClientRegistry` that points `ExtractorWithFallback` at the configured primary:
  ```python
  from baml_py import ClientRegistry

  async def _build_client_registry() -> ClientRegistry:
      cr = ClientRegistry()
      if settings.llm_primary_provider == "anthropic":
          cr.set_primary("AnthropicFallback")
      else:
          cr.set_primary("GPT4o")
      return cr

  # In extract_from_document:
  cr = await _build_client_registry()
  result = await b.ExtractIncome(doc=baml_input, baml_options={"client_registry": cr})
  ```
- Document the `LLM_PRIMARY_PROVIDER` env var in `.env.example` and README

## Notes

- The structlog `request_id` middleware approach uses `structlog.contextvars` which is thread-safe and async-safe — appropriate for FastAPI's async request handling
- For the Docker multi-stage build, `baml-cli generate` requires `baml-py` to be installed; install it in the `builder` stage only. The `runtime` stage only needs the generated `baml_client/` directory and `baml-py` runtime (not the CLI)
- The `ClientRegistry` approach does not change the BAML `.baml` files at all — it only overrides the client selection at runtime. This cleanly satisfies the "45-minute live modification" scenario mentioned in the interview where the interviewer asks: "The LLM provider you've been using just went down — walk us through how you'd add a fallback without breaking the API contract"

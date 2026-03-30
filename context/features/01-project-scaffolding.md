# Project Scaffolding & Configuration

> **Status: COMPLETE** ✅

## Overview

Establish the foundational project structure for the Document Extraction API. This phase sets up the FastAPI application skeleton, dependency manifest, environment configuration, and global exception handling infrastructure. Every subsequent phase builds on top of this foundation, so getting the structure right here prevents costly reorganization later.

## Requirements

- Create `pyproject.toml` as the single source of truth for dependencies and tooling config; do not use `requirements.txt`
- Dependencies: `fastapi`, `uvicorn[standard]`, `python-multipart`, `baml-py`, `pydantic-settings`, `python-dotenv`, `structlog`
- Dev/test dependencies: `pytest`, `pytest-asyncio`, `httpx`, `pyright`
- Set `asyncio_mode = "auto"` in `[tool.pytest.ini_options]` so async tests work without decorators
- Project layout:
  ```
  app/
  ├── __init__.py
  ├── main.py           # FastAPI app creation, router registration, exception handlers
  ├── config.py         # Settings(BaseSettings) — env-driven config
  ├── exceptions.py     # Custom exception hierarchy
  ├── api/
  │   ├── __init__.py
  │   └── submissions.py
  ├── schemas/
  │   ├── __init__.py
  │   └── responses.py
  └── services/
      ├── __init__.py
      ├── document.py
      └── extraction.py
  tests/
  ├── __init__.py
  ├── conftest.py
  ├── test_submissions.py
  ├── test_extraction.py
  └── test_document.py
  ```
- `app/config.py` — `Settings(BaseSettings)` with field `max_file_size_mb: int = 10`; use `env_file = ".env"` and `extra = "ignore"` so BAML's own env vars don't cause validation errors
- `app/main.py` — create FastAPI app, register the submissions router, add `GET /health` returning `{"status": "ok"}`, register global exception handlers (see Phase 5 for full handler list)
- `app/exceptions.py` — define `UnsupportedFormatError`, `ExtractionError`, `DocumentProcessingError` as plain Python exceptions (not HTTP exceptions) so they can be raised deep in service code and handled at the boundary
- `.env.example` — document all required env vars with placeholder values and comments
- `.gitignore` — must include: `baml_client/`, `.env`, `__pycache__/`, `.pytest_cache/`, `venv/`, `.venv/`

## Notes

- Keep `app/config.py` focused on app settings only; BAML reads `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` directly from the environment via its own env var resolution — do not re-read those in `Settings`
- `app/main.py` should import and register the router from `app/api/submissions.py` even if that file is a stub at this stage — keeps commits clean and the app always runnable
- `app/exceptions.py` custom exceptions are intentionally not subclasses of `HTTPException`; the translation to HTTP status codes happens only in the global handlers in `main.py`, which separates domain logic from transport concerns

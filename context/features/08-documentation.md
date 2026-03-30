# Documentation

## Overview

Write `README.md` and `DECISIONS.md` as first-class deliverables. The README must get a reviewer from `git clone` to a running API in under five minutes. DECISIONS.md must demonstrate genuine architectural reflection — it is the primary signal the interviewer uses to distinguish between an engineer who understands their code and one who generated it and moved on.

## Requirements

### `README.md`

Structure:

1. **Project title + one-sentence description**
2. **Quick start** — exactly three commands to go from clone to running:
   ```bash
   cp .env.example .env   # add your API keys
   docker-compose up --build
   # OR without Docker:
   pip install -e ".[dev]" && baml-cli generate && uvicorn app.main:app --reload
   ```
3. **API reference** — table of endpoints with method, path, description, and a `curl` example for `POST /submissions`:
   ```bash
   curl -X POST http://localhost:8000/submissions \
     -F "file=@/path/to/pay_stub.pdf"
   ```
4. **Response shape** — show a success example and a partial/error example as JSON code blocks
5. **Configuration** — table of all env vars, their defaults, and what they control
6. **Running tests** — `pytest -v` with a note that no API keys are required (all tests use mocked LLM)
7. **Architecture overview** — short prose (3–4 sentences) + ASCII diagram:
   ```
   POST /submissions
        │
        ▼
   document.py ──► magic byte validation ──► BAML Image/Pdf
        │
        ▼
   extraction.py ──► b.ExtractIncome(doc) ──► LLM (GPT-4o → Claude fallback)
        │
        ▼
   post-validation ──► SubmissionResponse (success / partial / error)
   ```
8. **AI tools used** — honest disclosure of what was used and how

### `DECISIONS.md`

Must address each of the four required topics:

**1. Why you built it this way**
- Why BAML over the raw OpenAI SDK: BAML provides native `pdf`/`image` input types, auto-generated Pydantic models from the schema, built-in fallback client strategies, and structured output parsing that handles malformed JSON — all things that would be boilerplate otherwise. The explicit mention in the brief made it the right call to demonstrate tool awareness.
- Why optional fields in BAML + required validation in Python: making fields optional in BAML lets the parser return a partial result rather than raising on missing data, which enables per-field error reporting. If fields were required in BAML, any missing field would collapse the whole extraction to an error, losing whatever was successfully extracted.
- Why LangGraph was excluded: for a single synchronous extraction step, a graph adds ceremony without benefit. LangGraph becomes appropriate if the pipeline grows to multi-step: classify document type → extract type-specific fields → verify against an external source. The current design makes that extension straightforward.
- Adding a second document type (e.g. government ID): add a `GovernmentIdExtraction` class and `ExtractGovernmentId` function in `baml_src/`; add a document-type classifier step; route to the appropriate extraction function. The service layer's `extract_from_document` would become a dispatcher. No changes to the API contract.

**2. Where it's fragile**
- Single-pass extraction with no retry on partial results: if the LLM returns partial output once, the API returns `"partial"` without retrying with a clarifying prompt. In production, a retry with "field X was missing — please look more carefully at the document" would improve recall.
- English-only: the prompt is written in English and the schema descriptions are English. Non-English documents may produce lower-quality extractions or fail entirely.
- Large documents: a 50-page PDF will hit token limits. The current implementation sends the entire document. Production would need page-count detection and truncation or page selection logic.
- Image quality: low-resolution scans or handwritten documents are passed directly to the LLM with no preprocessing (no OCR, no deskewing). Quality of extraction degrades proportionally.

**3. One thing you'd refactor**
- Point to `app/services/extraction.py` — specifically the `extract_from_document` function
- The function currently does three things: format conversion (delegated), LLM call, and post-validation. As the number of document types grows, the post-validation block will become a large conditional. The refactor: introduce a `PostValidator` protocol with a single `validate(result: IncomeExtraction) -> list[ErrorDetail]` method; implement a `IncomeExtractionValidator` class; inject it into `extract_from_document`. This separates validation policy from orchestration and makes each validator unit-testable in isolation.

**4. A judgment call made under uncertainty**
- The decision to return HTTP 200 for `"partial"` and `"error"` extraction statuses rather than HTTP 422/500
- Argument for 200: the API contract fulfilled its obligation (the document was received and processed); the extraction status is a business outcome, not an HTTP protocol failure. Using 200 with a structured body lets callers handle both success and failure with the same response-parsing code path.
- Argument for 4xx: `"error"` status arguably represents a processing failure the client indirectly caused (by uploading an unreadable document), making 422 semantically appropriate. Some API consumers rely on HTTP status codes for routing in gateway layers.
- Decision made: 200 for extraction outcomes, 422 only for `UnsupportedFormatError` (which is unambiguously a client input error). Would go the other direction if the API were consumed by non-technical gateway tooling that routes on status code alone.

## Notes

- DECISIONS.md should be ~1 page; use bullet points — prose sections should be 2–4 sentences max
- README quick start must be accurate and runnable against the actual codebase at time of submission — test it
- Do not list every file in the README architecture section; keep it high-level with the ASCII diagram doing the visual work

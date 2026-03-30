# DECISIONS.md

## Why I Built It This Way

- **LangGraph for orchestration.** The extraction pipeline is modeled as a LangGraph `StateGraph` with three nodes: `validate_document` → `extract_via_llm` → `post_validate`. This adds real value: the graph makes the pipeline's control flow explicit and extensible. Adding a document-type classifier or a retry-with-clarification step is just a new node and edge — no refactoring of function call chains. The conditional edge after `extract_via_llm` already demonstrates this: if the LLM fails, the graph short-circuits to END without running post-validation.

- **Async job-based extraction.** `POST /submissions` returns 202 with a `job_id` immediately. Extraction runs in the background via `asyncio.create_task`. Clients poll `GET /submissions/{job_id}` for results. This decouples upload latency from LLM processing time, is the natural pattern for production (swap the in-memory store for Redis/DB), and matches the instructions' bonus criteria for async processing.

- **BAML for structured LLM calls.** BAML provides native `pdf`/`image` input types, auto-generated Pydantic models from the schema, built-in fallback client strategies, and structured output parsing that handles malformed JSON — all things that would be hand-rolled boilerplate otherwise. The brief explicitly mentioned BAML, so leaning into it demonstrated tool awareness while genuinely simplifying the codebase.

- **Adding a second document type (e.g. government ID):** Add a `GovernmentIdExtraction` class and `ExtractGovernmentId` function in `baml_src/`; add a `classify_document` node to the LangGraph pipeline that routes to the appropriate extraction node via conditional edges. The service layer's graph already supports this branching — just add nodes and edges. No changes to the API contract — `SubmissionResponse` already supports variable fields via its optional `ExtractionData` shape.

## Where It's Fragile

- **Single-pass extraction with no retry on partial results.** If the LLM returns partial output, the API returns `"partial"` without retrying with a clarifying prompt. In production, a retry with "field X was missing — please look more carefully at the document" would improve recall.

- **English-only.** The prompt and schema descriptions are in English. Non-English documents may produce lower-quality extractions or fail entirely.

- **Large documents.** A 50-page PDF will hit token limits. The current implementation sends the entire document. Production would need page-count detection and selective page extraction.

- **No preprocessing.** Low-resolution scans, rotated images, or handwritten documents pass directly to the LLM with no OCR or deskewing. Extraction quality degrades proportionally.

## One Thing I'd Refactor

The in-memory job store (`app/services/jobs.py`) is the obvious production gap. It uses a plain `dict` — jobs vanish on restart, there's no TTL/cleanup, and it doesn't scale past a single process. The fix: swap the `_jobs` dict for a Redis-backed store (or PostgreSQL) behind the same `create_job`/`get_job` interface. The rest of the codebase wouldn't change.

## A Judgment Call Under Uncertainty

**Treating extraction outcomes as business results, not HTTP errors.**

The async job flow means `POST /submissions` always returns 202 (accepted), and `GET /submissions/{job_id}` always returns 200 with the job state. The extraction outcome — `"success"`, `"partial"`, or `"error"` — lives inside the job result body, not as an HTTP status code.

- **Argument for this approach:** The API fulfilled its obligation — the document was received and processed. The extraction outcome is a business result, not a protocol failure. Callers parse the same response shape regardless of outcome. Most document processing APIs follow this pattern.

- **Argument against:** Some API consumers rely on HTTP status codes for gateway-level routing or alerting. A `"partial"` result could justify a 207 or 422 at the HTTP level.

- **Decision:** HTTP status codes reflect the *transport-level* outcome (202 = accepted, 200 = job found, 404 = unknown job). Extraction outcomes are expressed in the response body. The one exception is `UnsupportedFormatError` — caught *before* job creation, returned as a direct 422. This is unambiguously a client input error, not an extraction outcome.

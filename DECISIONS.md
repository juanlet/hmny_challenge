# DECISIONS.md

## Why I Built It This Way

- **BAML over raw OpenAI SDK.** BAML provides native `pdf`/`image` input types, auto-generated Pydantic models from the schema, built-in fallback client strategies, and structured output parsing that handles malformed JSON — all things that would be hand-rolled boilerplate otherwise. The brief explicitly mentioned BAML, so leaning into it demonstrated tool awareness while genuinely simplifying the codebase.

- **Optional fields in BAML, required validation in Python.** Making every field `?` (optional) in the BAML schema lets the parser return a partial result rather than raising on missing data. This enables per-field error reporting — if `gross_income` is missing but `employer_name` was extracted, the caller gets both the data and the specific failures. If fields were required in BAML, any single missing field collapses the entire extraction into an error.

- **LangGraph excluded.** For a single synchronous extraction step, a graph framework adds ceremony without benefit. LangGraph becomes worthwhile when the pipeline grows to multi-step: classify document type → extract type-specific fields → verify against an external source. The current design's `extract_from_document()` function is the natural extension point for that.

- **Adding a second document type (e.g. government ID):** Add a `GovernmentIdExtraction` class and `ExtractGovernmentId` function in `baml_src/`; add a document-type classifier step; route to the appropriate extraction function. The service layer's `extract_from_document` would become a dispatcher. No changes to the API contract — `SubmissionResponse` already supports variable fields via its optional `ExtractionData` shape.

## Where It's Fragile

- **Single-pass extraction with no retry on partial results.** If the LLM returns partial output, the API returns `"partial"` without retrying with a clarifying prompt. In production, a retry with "field X was missing — please look more carefully at the document" would improve recall.

- **English-only.** The prompt and schema descriptions are in English. Non-English documents may produce lower-quality extractions or fail entirely.

- **Large documents.** A 50-page PDF will hit token limits. The current implementation sends the entire document. Production would need page-count detection and selective page extraction.

- **No preprocessing.** Low-resolution scans, rotated images, or handwritten documents pass directly to the LLM with no OCR or deskewing. Extraction quality degrades proportionally.

## One Thing I'd Refactor

I'd refactor `extract_from_document()` in `app/services/extraction.py`. It currently handles three responsibilities: format conversion (delegated), LLM invocation, and post-validation. As document types multiply, the validation block grows into a long conditional.

**The fix:** Introduce a `PostValidator` protocol with a `validate(result) -> list[ErrorDetail]` method. Implement `IncomeExtractionValidator` as one concrete class with the required-field and negative-income checks. Inject validators into `extract_from_document`. This separates validation policy from orchestration, makes each validator independently testable, and lets new document types bring their own validation rules without touching the core function.

## A Judgment Call Under Uncertainty

**Returning HTTP 200 for `"partial"` and `"error"` extraction statuses** instead of 422/500.

- **Argument for 200:** The API fulfilled its obligation — the document was received and processed. The extraction outcome is a business result, not a protocol failure. Using 200 with a structured body lets callers handle success and failure with the same response-parsing code path. Most document processing APIs follow this pattern.

- **Argument for 4xx:** `"error"` status arguably represents a processing failure the client indirectly caused (uploading an unreadable document), making 422 semantically appropriate. Some API consumers rely on HTTP status codes for gateway-level routing.

- **Decision:** 200 for extraction outcomes, 422 only for `UnsupportedFormatError` (unambiguously a client input error). I'd reconsider if the API were consumed primarily by gateway tooling that routes on status codes.

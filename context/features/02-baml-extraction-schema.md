# BAML Schema & Extraction Function

## Overview

Define all BAML types and the core LLM extraction function using BAML's domain-specific language. BAML compiles to a `baml_client/` Python package that provides fully type-safe, auto-parsed calls to the LLM — no manual JSON schema wrangling, no regex parsing of LLM output. This phase establishes both the output schema the LLM must conform to and the prompt that guides its extraction behavior.

## Requirements

- Run `baml-cli init` to scaffold `baml_src/` with a default `generators.baml`; update the generator to output to `./baml_client`
- Create `baml_src/clients.baml`:
  - Define a primary client `GPT4o` using `openai/gpt-4o` — best multimodal model for vision + structured extraction
  - Define a fallback client `AnthropicFallback` using `anthropic/claude-sonnet-4-20250514`
  - Define a composite client `ExtractorWithFallback` using `provider fallback` with `strategy ["GPT4o", "AnthropicFallback"]`
  - Both primary clients must read API keys from environment variables using BAML's `env("OPENAI_API_KEY")` / `env("ANTHROPIC_API_KEY")` syntax
- Create `baml_src/extraction.baml` with the following types:
  - `enum PayFrequency` — values: `Weekly`, `BiWeekly`, `Monthly`, `Other`; add `@description` annotations for clarity
  - `class IncomePeriod` — `start_date string @description("ISO 8601 date, e.g. 2024-01-01")`, `end_date string @description("ISO 8601 date, e.g. 2024-01-31")`
  - `class IncomeExtraction` — all fields **optional** (`?`) so the LLM can return null rather than hallucinate:
    - `employer_name string?`
    - `employee_name string?`
    - `gross_income float?` with `@description("Numeric value only, no currency symbols")`
    - `net_income float?`
    - `pay_frequency PayFrequency?`
    - `income_period IncomePeriod?`
    - `document_type string?` with `@description("One of: pay_stub, offer_letter, bank_statement, other")`
    - `currency string? @description("ISO 4217 code, e.g. USD")`
    - `confidence_notes string[] @description("List any fields that were ambiguous, unclear, or estimated")`
  - `function ExtractIncome(doc: image | pdf) -> IncomeExtraction` using the `ExtractorWithFallback` client
- Prompt design for `ExtractIncome`:
  - Use a system-role block (`_.role("system")`) establishing the LLM as a financial document analyst
  - Explicitly instruct: return `null` for any field not clearly present in the document — do not guess or infer
  - Explicitly instruct: `gross_income` and `net_income` must be numeric values only (e.g. `3000.00`), never text like "three thousand dollars"
  - Ask the model to populate `confidence_notes` with any ambiguities, illegible text, or fields it was uncertain about
  - Include `{{ ctx.output_format }}` so BAML injects the schema constraint automatically
  - Include the document via `{{ doc }}`
- Run `baml-cli generate` after authoring `.baml` files to produce `baml_client/`
- Add `baml_client/` to `.gitignore` — it is a build artifact, generated on `baml-cli generate`

## CRITICAL: BAML `image | pdf` union input

BAML supports union types as function parameters. `function ExtractIncome(doc: image | pdf)` is valid syntax. However, the Python caller must pass the correct type:

```python
from baml_py import Image, Pdf

# For images
baml_input = Image.from_base64("image/png", base64_str)

# For PDFs
baml_input = Pdf.from_base64("application/pdf", base64_str)

# Calling the function — BAML resolves the union at runtime
result = await b.ExtractIncome(doc=baml_input)
```

If BAML's union dispatch does not work as expected during testing, fall back to two separate functions (`ExtractIncomeFromImage`, `ExtractIncomeFromPdf`) and dispatch in the service layer based on MIME type — the calling code is identical, just routed differently.

## CRITICAL: Optional fields vs. post-validation

All `IncomeExtraction` fields are optional in the BAML schema intentionally. This is a deliberate two-layer design:

1. **BAML layer** — parses whatever the LLM returns into a typed Python object; fields the LLM omits become `None`
2. **Python service layer** (Phase 4) — enforces business rules: `employer_name`, `gross_income`, and `pay_frequency` are *required for a successful extraction*; if any are `None`, the service generates a structured `ErrorDetail` with `error_type="missing_field"`

Making fields required in BAML itself would cause BAML to raise a parse error rather than returning a partial result — losing information about *which* fields were missing.

## Notes

- `baml_client/` is auto-generated and must never be hand-edited; the source of truth is `baml_src/`
- The `confidence_notes` field serves as a soft confidence signal: instead of a numeric score that the LLM calibrates poorly, natural-language self-reporting is more actionable for downstream consumers
- `document_type` is returned by the LLM as a string rather than an enum so extraction still succeeds on unusual document types without a schema failure
- BAML's fallback client transparently retries on the second provider if the first raises any exception (network error, rate limit, invalid response) — this satisfies the bonus LLM fallback chain requirement with zero extra application code

"""LangGraph extraction pipeline.

Nodes:
  validate_document → extract_via_llm → post_validate

Each node reads/writes to a shared TypedDict state so LangGraph
handles orchestration, error propagation, and (in the future)
branching for document-type-specific extraction.
"""

import os
import time
from typing import Any, TypedDict, Union

import structlog
from baml_py import ClientRegistry, Image, Pdf
from baml_py.baml_py import BamlError
from langgraph.graph import END, START, StateGraph

from baml_client.async_client import b

from app.config import settings
from app.schemas.responses import (
    ErrorDetail,
    ExtractionData,
    IncomePeriodData,
    SubmissionResponse,
)
from app.services.document import validate_and_convert

logger = structlog.get_logger()

REQUIRED_FIELDS = ["employer_name", "gross_income", "pay_frequency"]

_PROVIDER_TO_CLIENT = {
    "openai": "GPT4o",
    "anthropic": "AnthropicSonnet",
    "google": "Gemini",
    "xai": "Grok",
}

_PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "xai": "XAI_API_KEY",
}

_FALLBACK_ORDER = ["openai", "anthropic", "google", "xai"]


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class _ExtractionBase(TypedDict):
    # Always present — provided by run_extraction at graph invocation
    content: bytes
    filename: str
    start_time: float


class ExtractionState(_ExtractionBase, total=False):
    # Added by validate_document node
    mime_type: str
    baml_input: Union[Image, Pdf]
    # Added by extract_via_llm node
    raw_result: Any
    model_used: str
    # Added by post_validate (or error short-circuit)
    response: SubmissionResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_real_key(value: str | None) -> bool:
    if not value:
        return False
    lower = value.lower()
    return not ("your-" in lower or "here" in lower or "replace" in lower or lower.startswith("sk-placeholder"))


def _detect_provider() -> str:
    configured = settings.llm_primary_provider
    if configured != "auto":
        return configured
    for provider in _FALLBACK_ORDER:
        if _is_real_key(os.environ.get(_PROVIDER_KEY_ENV[provider])):
            return provider
    return "openai"


def _build_client_registry() -> tuple[ClientRegistry, str]:
    provider = _detect_provider()
    cr = ClientRegistry()
    cr.add_llm_client("GPT4o", "openai", {
        "model": settings.openai_model,
        "api_key": os.environ.get("OPENAI_API_KEY", ""),
    })
    cr.add_llm_client("AnthropicSonnet", "anthropic", {
        "model": settings.anthropic_model,
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    })
    cr.add_llm_client("Gemini", "google-ai", {
        "model": settings.gemini_model,
        "api_key": os.environ.get("GOOGLE_API_KEY", ""),
    })
    cr.add_llm_client("Grok", "openai-generic", {
        "model": settings.xai_model,
        "base_url": "https://api.x.ai/v1",
        "api_key": os.environ.get("XAI_API_KEY", ""),
    })
    client_name = _PROVIDER_TO_CLIENT[provider]
    cr.set_primary(client_name)
    return cr, client_name


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def validate_document(state: ExtractionState) -> dict:
    """Validate format via magic bytes, convert to BAML Image/Pdf."""
    mime_type, baml_input = validate_and_convert(state["content"], state["filename"])
    logger.info("document_validated", mime_type=mime_type)
    return {"mime_type": mime_type, "baml_input": baml_input}


async def extract_via_llm(state: ExtractionState) -> dict:
    """Call BAML extraction with the configured LLM provider."""
    cr, model_used = _build_client_registry()
    try:
        result = await b.ExtractIncome(
            doc=state["baml_input"],
            baml_options={"client_registry": cr},
        )
    except BamlError as exc:
        elapsed_ms = round((time.monotonic() - state["start_time"]) * 1000)
        logger.error("extraction_failed", error=str(exc))
        return {
            "raw_result": None,
            "model_used": "unknown",
            "response": SubmissionResponse(
                status="error",
                data=None,
                errors=[ErrorDetail(field=None, error_type="extraction_failed", message=str(exc))],
                metadata={"model_used": "unknown", "processing_time_ms": elapsed_ms},
            ),
        }
    return {"raw_result": result, "model_used": model_used}


def post_validate(state: ExtractionState) -> dict:
    """Check required fields and business rules, build final response."""
    # If extract_via_llm already built an error response, pass through.
    if state.get("response") is not None:
        return {}

    result = state["raw_result"]
    model_used = state["model_used"]
    errors: list[ErrorDetail] = []

    for field in REQUIRED_FIELDS:
        if getattr(result, field) is None:
            errors.append(ErrorDetail(
                field=field,
                error_type="missing_field",
                message=f"'{field}' could not be extracted from the document",
            ))

    if result.gross_income is not None and result.gross_income <= 0:
        errors.append(ErrorDetail(
            field="gross_income",
            error_type="validation_error",
            message="gross_income must be a positive number",
            raw_value=str(result.gross_income),
        ))

    income_period = None
    if result.income_period is not None:
        income_period = IncomePeriodData(
            start_date=result.income_period.start_date,
            end_date=result.income_period.end_date,
        )

    data = ExtractionData(
        employer_name=result.employer_name,
        employee_name=result.employee_name,
        gross_income=result.gross_income,
        net_income=result.net_income,
        pay_frequency=result.pay_frequency.value if result.pay_frequency else None,
        income_period=income_period,
        document_type=result.document_type,
        currency=result.currency,
        confidence_notes=list(result.confidence_notes) if result.confidence_notes else [],
    )

    status = "success" if not errors else "partial"
    elapsed_ms = round((time.monotonic() - state["start_time"]) * 1000)
    missing = [e.field for e in errors if e.error_type == "missing_field"]
    logger.info("extraction_complete", status=status, missing_fields=missing)

    return {
        "response": SubmissionResponse(
            status=status,
            data=data,
            errors=errors,
            metadata={"model_used": model_used, "processing_time_ms": elapsed_ms},
        )
    }


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def _should_skip_post_validate(state: ExtractionState) -> str:
    """If LLM node already produced a terminal response, go to END."""
    if state.get("response") is not None:
        return END
    return "post_validate"


workflow = StateGraph(ExtractionState)
workflow.add_node("validate_document", validate_document)
workflow.add_node("extract_via_llm", extract_via_llm)
workflow.add_node("post_validate", post_validate)

workflow.add_edge(START, "validate_document")
workflow.add_edge("validate_document", "extract_via_llm")
workflow.add_conditional_edges("extract_via_llm", _should_skip_post_validate)
workflow.add_edge("post_validate", END)

extraction_graph = workflow.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_extraction(content: bytes, filename: str) -> SubmissionResponse:
    """Run the full extraction pipeline through LangGraph."""
    logger.info("document_received", filename=filename, content_length=len(content))
    state = await extraction_graph.ainvoke({
        "content": content,
        "filename": filename,
        "start_time": time.monotonic(),
    })
    return state["response"]

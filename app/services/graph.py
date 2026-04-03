"""LangGraph extraction pipeline.

Fixed 4-node graph:
  START → validate_document → classify_document → extract → post_validate → END

Document-type-specific logic (BAML function, required fields, validators,
response builder) lives in a DOCUMENT_CONFIGS registry.  Adding a new
document type requires zero graph changes — just register a new config entry.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict, Union

import structlog
from baml_py import ClientRegistry, Image, Pdf
from baml_py.baml_py import BamlError
from langgraph.graph import END, START, StateGraph

from baml_client.async_client import b

from app.config import settings
from app.schemas.responses import (
    DeductionLineItemData,
    EarningsLineItemData,
    ErrorDetail,
    ExtractionData,
    IncomePeriodData,
    SubmissionResponse,
    TaxWithholdingData,
    W2EarningsData,
)
from app.services.document import validate_and_convert

logger = structlog.get_logger()

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
    content: bytes
    filename: str
    start_time: float


class ExtractionState(_ExtractionBase, total=False):
    mime_type: str
    baml_input: Union[Image, Pdf]
    document_category: str  # registry key, e.g. "Income", "W2Earnings"
    raw_result: Any
    model_used: str
    response: SubmissionResponse


# ---------------------------------------------------------------------------
# Document-type registry
# ---------------------------------------------------------------------------

# Type alias for a validator: receives the raw BAML result, returns a list of errors
ValidatorFn = Callable[[Any], list[ErrorDetail]]
# Type alias for a data builder: receives the raw BAML result, returns response data
BuildDataFn = Callable[[Any], ExtractionData | W2EarningsData]
@dataclass(frozen=True)
class DocumentTypeConfig:
    extract_fn_name: str  # method name on `b`, e.g. "ExtractIncome"
    required_fields: list[str]
    validators: list[ValidatorFn] = field(default_factory=list)
    build_data: BuildDataFn = lambda r: r  # type: ignore[assignment]


# --- Validator factories ---

def _check_positive(field_name: str) -> ValidatorFn:
    """Return a validator that checks a numeric field is positive."""
    def _validate(result: Any) -> list[ErrorDetail]:
        value = getattr(result, field_name, None)
        if value is not None and value <= 0:
            return [ErrorDetail(
                field=field_name,
                error_type="validation_error",
                message=f"{field_name} must be a positive number",
                raw_value=str(value),
            )]
        return []
    return _validate


# --- Data builders ---

def _build_income_data(result: Any) -> ExtractionData:
    income_period = None
    if result.income_period is not None:
        income_period = IncomePeriodData(
            start_date=result.income_period.start_date,
            end_date=result.income_period.end_date,
        )
    return ExtractionData(
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


def _build_w2_data(result: Any) -> W2EarningsData:
    tax_withholding = None
    if result.tax_withholding is not None:
        tax_withholding = TaxWithholdingData(
            federal_income_tax=result.tax_withholding.federal_income_tax,
            social_security_tax=result.tax_withholding.social_security_tax,
            medicare_tax=result.tax_withholding.medicare_tax,
            state_income_tax=result.tax_withholding.state_income_tax,
        )
    pay_period = None
    if result.pay_period is not None:
        pay_period = IncomePeriodData(
            start_date=result.pay_period.start_date,
            end_date=result.pay_period.end_date,
        )
    earnings = [
        EarningsLineItemData(
            description=e.description, hours=e.hours, rate=e.rate,
            current_amount=e.current_amount, ytd_amount=e.ytd_amount,
        )
        for e in (result.earnings or [])
    ]
    deductions = [
        DeductionLineItemData(
            description=d.description,
            current_amount=d.current_amount, ytd_amount=d.ytd_amount,
        )
        for d in (result.deductions or [])
    ]
    return W2EarningsData(
        employer_name=result.employer_name,
        employer_ein=result.employer_ein,
        employer_address=result.employer_address,
        employee_name=result.employee_name,
        employee_ssn=result.employee_ssn,
        employee_address=result.employee_address,
        employee_id=result.employee_id,
        department=result.department,
        wages_tips_compensation=result.wages_tips_compensation,
        social_security_wages=result.social_security_wages,
        medicare_wages=result.medicare_wages,
        tax_withholding=tax_withholding,
        retirement_plan=result.retirement_plan,
        box_12_codes=list(result.box_12_codes) if result.box_12_codes else [],
        control_number=result.control_number,
        allocated_tips=result.allocated_tips,
        dependent_care=result.dependent_care,
        state=result.state,
        state_id=result.state_id,
        state_wages=result.state_wages,
        state_tax=result.state_tax,
        pay_period=pay_period,
        pay_date=result.pay_date,
        pay_frequency=result.pay_frequency.value if result.pay_frequency else None,
        earnings=earnings,
        deductions=deductions,
        gross_pay=result.gross_pay,
        net_pay=result.net_pay,
        tax_year=result.tax_year,
        document_type=result.document_type,
        currency=result.currency,
        confidence_notes=list(result.confidence_notes) if result.confidence_notes else [],
    )


# --- Registry: add new document types here ---

DOCUMENT_CONFIGS: dict[str, DocumentTypeConfig] = {
    "Income": DocumentTypeConfig(
        extract_fn_name="ExtractIncome",
        required_fields=["employer_name", "gross_income", "pay_frequency"],
        validators=[_check_positive("gross_income")],
        build_data=_build_income_data,
    ),
    "W2Earnings": DocumentTypeConfig(
        extract_fn_name="ExtractW2Earnings",
        required_fields=["employer_name", "wages_tips_compensation", "employee_name"],
        validators=[_check_positive("wages_tips_compensation"), _check_positive("gross_pay")],
        build_data=_build_w2_data,
    ),
}

DEFAULT_CATEGORY = "Income"


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
# Graph nodes (fixed — never changes when adding document types)
# ---------------------------------------------------------------------------

def validate_document(state: ExtractionState) -> dict:
    """Validate format via magic bytes, convert to BAML Image/Pdf."""
    mime_type, baml_input = validate_and_convert(state["content"], state["filename"])
    logger.info("document_validated", mime_type=mime_type)
    return {"mime_type": mime_type, "baml_input": baml_input}


async def classify_document(state: ExtractionState) -> dict:
    """Classify the document type via LLM to route extraction."""
    cr, _ = _build_client_registry()
    try:
        doc_type = await b.ClassifyDocument(
            doc=state["baml_input"],
            baml_options={"client_registry": cr},
        )
        category = doc_type.value
    except BamlError:
        category = DEFAULT_CATEGORY
    logger.info("document_classified", category=category)
    return {"document_category": category}


async def extract(state: ExtractionState) -> dict:
    """Call the BAML extraction function for the classified document type."""
    category = state.get("document_category", DEFAULT_CATEGORY)
    config = DOCUMENT_CONFIGS[category]
    cr, model_used = _build_client_registry()
    extract_fn = getattr(b, config.extract_fn_name)
    try:
        result = await extract_fn(
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
    """Check required fields, run validators, build response — all data-driven."""
    if state.get("response") is not None:
        return {}

    category = state.get("document_category", DEFAULT_CATEGORY)
    config = DOCUMENT_CONFIGS[category]
    result = state["raw_result"]
    model_used = state["model_used"]
    errors: list[ErrorDetail] = []

    # Required-field checks
    for field_name in config.required_fields:
        if getattr(result, field_name, None) is None:
            errors.append(ErrorDetail(
                field=field_name,
                error_type="missing_field",
                message=f"'{field_name}' could not be extracted from the document",
            ))

    # Business-rule validators
    for validator in config.validators:
        errors.extend(validator(result))

    data = config.build_data(result)
    status = "success" if not errors else "partial"
    elapsed_ms = round((time.monotonic() - state["start_time"]) * 1000)
    missing = [e.field for e in errors if e.error_type == "missing_field"]
    logger.info("extraction_complete", status=status, extraction_type=category, missing_fields=missing)

    return {
        "response": SubmissionResponse(
            status=status,
            data=data,
            errors=errors,
            metadata={"model_used": model_used, "processing_time_ms": elapsed_ms, "extraction_type": category},
        )
    }


# ---------------------------------------------------------------------------
# Build the graph (fixed topology — never changes)
# ---------------------------------------------------------------------------

def _should_skip_post_validate(state: ExtractionState) -> str:
    if state.get("response") is not None:
        return END
    return "post_validate"


workflow = StateGraph(ExtractionState)
workflow.add_node("validate_document", validate_document)
workflow.add_node("classify_document", classify_document)
workflow.add_node("extract", extract)
workflow.add_node("post_validate", post_validate)

workflow.add_edge(START, "validate_document")
workflow.add_edge("validate_document", "classify_document")
workflow.add_edge("classify_document", "extract")
workflow.add_conditional_edges("extract", _should_skip_post_validate)
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

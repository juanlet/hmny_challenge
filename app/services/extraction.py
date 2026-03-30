import time

import structlog
from baml_py import ClientRegistry
from baml_py.baml_py import BamlError

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
}


def _build_client_registry() -> ClientRegistry:
    cr = ClientRegistry()
    client_name = _PROVIDER_TO_CLIENT.get(
        settings.llm_primary_provider, "GPT4o"
    )
    cr.set_primary(client_name)
    return cr


async def extract_from_document(
    content: bytes, filename: str
) -> SubmissionResponse:
    """Validate a document, call the LLM via BAML, and return a structured response."""
    start = time.monotonic()

    logger.info("document_received", filename=filename, content_length=len(content))

    # Step 1: validate format and convert to BAML input (raises UnsupportedFormatError)
    mime_type, baml_input = validate_and_convert(content, filename)
    logger.info("document_validated", mime_type=mime_type)

    # Step 2: call BAML extraction
    cr = _build_client_registry()
    model_used = _PROVIDER_TO_CLIENT.get(settings.llm_primary_provider, "GPT4o")
    try:
        result = await b.ExtractIncome(doc=baml_input, baml_options={"client_registry": cr})
    except BamlError as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        logger.error("extraction_failed", error=str(exc))
        return SubmissionResponse(
            status="error",
            data=None,
            errors=[
                ErrorDetail(
                    field=None,
                    error_type="extraction_failed",
                    message=str(exc),
                )
            ],
            metadata={"model_used": "unknown", "processing_time_ms": elapsed_ms},
        )

    # Step 3: post-validate required fields
    errors: list[ErrorDetail] = []
    for field in REQUIRED_FIELDS:
        if getattr(result, field) is None:
            errors.append(
                ErrorDetail(
                    field=field,
                    error_type="missing_field",
                    message=f"'{field}' could not be extracted from the document",
                )
            )

    # Step 4: business-rule validation
    if result.gross_income is not None and result.gross_income <= 0:
        errors.append(
            ErrorDetail(
                field="gross_income",
                error_type="validation_error",
                message="gross_income must be a positive number",
                raw_value=str(result.gross_income),
            )
        )

    # Step 5: build response data
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
    elapsed_ms = round((time.monotonic() - start) * 1000)
    missing = [e.field for e in errors if e.error_type == "missing_field"]
    logger.info("extraction_complete", status=status, missing_fields=missing)

    return SubmissionResponse(
        status=status,
        data=data,
        errors=errors,
        metadata={"model_used": model_used, "processing_time_ms": elapsed_ms},
    )

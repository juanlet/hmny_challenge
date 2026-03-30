import time

from baml_py.baml_py import BamlError

from baml_client.async_client import b

from app.schemas.responses import (
    ErrorDetail,
    ExtractionData,
    IncomePeriodData,
    SubmissionResponse,
)
from app.services.document import validate_and_convert

REQUIRED_FIELDS = ["employer_name", "gross_income", "pay_frequency"]


async def extract_from_document(
    content: bytes, filename: str
) -> SubmissionResponse:
    """Validate a document, call the LLM via BAML, and return a structured response."""
    start = time.monotonic()

    # Step 1: validate format and convert to BAML input (raises UnsupportedFormatError)
    _mime_type, baml_input = validate_and_convert(content, filename)

    # Step 2: call BAML extraction
    try:
        result = await b.ExtractIncome(doc=baml_input)
    except BamlError as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000)
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

    return SubmissionResponse(
        status=status,
        data=data,
        errors=errors,
        metadata={"model_used": "gpt-4o", "processing_time_ms": elapsed_ms},
    )

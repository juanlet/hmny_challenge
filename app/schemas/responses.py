from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ErrorType = Literal[
    "missing_field", "validation_error", "unsupported_format", "extraction_failed"
]


class ErrorDetail(BaseModel):
    field: str | None
    error_type: ErrorType
    message: str
    raw_value: str | None = None


class IncomePeriodData(BaseModel):
    start_date: str
    end_date: str


class ExtractionData(BaseModel):
    employer_name: str | None = None
    employee_name: str | None = None
    gross_income: float | None = None
    net_income: float | None = None
    pay_frequency: str | None = None
    income_period: IncomePeriodData | None = None
    document_type: str | None = None
    currency: str | None = None
    confidence_notes: list[str] = []


class SubmissionResponse(BaseModel):
    status: Literal["success", "partial", "error"]
    data: ExtractionData | None = None
    errors: list[ErrorDetail] = []
    metadata: dict[str, str | int | float] = {}

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

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


# ---------------------------------------------------------------------------
# Income extraction (pay stubs, offer letters, bank statements)
# ---------------------------------------------------------------------------

class ExtractionData(BaseModel):
    extraction_type: Literal["income"] = "income"
    employer_name: str | None = None
    employee_name: str | None = None
    gross_income: float | None = None
    net_income: float | None = None
    pay_frequency: str | None = None
    income_period: IncomePeriodData | None = None
    document_type: str | None = None
    currency: str | None = None
    confidence_notes: list[str] = []


# ---------------------------------------------------------------------------
# W-2 / Earnings Statement extraction
# ---------------------------------------------------------------------------

class TaxWithholdingData(BaseModel):
    federal_income_tax: float | None = None
    social_security_tax: float | None = None
    medicare_tax: float | None = None
    state_income_tax: float | None = None


class EarningsLineItemData(BaseModel):
    description: str | None = None
    hours: float | None = None
    rate: float | None = None
    current_amount: float | None = None
    ytd_amount: float | None = None


class DeductionLineItemData(BaseModel):
    description: str | None = None
    current_amount: float | None = None
    ytd_amount: float | None = None


class W2EarningsData(BaseModel):
    extraction_type: Literal["w2_earnings"] = "w2_earnings"

    # Employer
    employer_name: str | None = None
    employer_ein: str | None = None
    employer_address: str | None = None

    # Employee
    employee_name: str | None = None
    employee_ssn: str | None = None
    employee_address: str | None = None
    employee_id: str | None = None
    department: str | None = None

    # W-2 Financials
    wages_tips_compensation: float | None = None
    social_security_wages: float | None = None
    medicare_wages: float | None = None
    tax_withholding: TaxWithholdingData | None = None

    # Benefits / Codes
    retirement_plan: bool | None = None
    box_12_codes: list[str] = []
    control_number: str | None = None
    allocated_tips: float | None = None
    dependent_care: float | None = None

    # State
    state: str | None = None
    state_id: str | None = None
    state_wages: float | None = None
    state_tax: float | None = None

    # Earnings Statement
    pay_period: IncomePeriodData | None = None
    pay_date: str | None = None
    pay_frequency: str | None = None
    earnings: list[EarningsLineItemData] = []
    deductions: list[DeductionLineItemData] = []
    gross_pay: float | None = None
    net_pay: float | None = None

    # Meta
    tax_year: int | None = None
    document_type: str | None = None
    currency: str | None = None
    confidence_notes: list[str] = []


# ---------------------------------------------------------------------------
# Discriminated union — clients check data.extraction_type
# ---------------------------------------------------------------------------

AnyExtractionData = Annotated[
    Union[ExtractionData, W2EarningsData],
    Field(discriminator="extraction_type"),
]


class SubmissionResponse(BaseModel):
    status: Literal["success", "partial", "error"]
    data: AnyExtractionData | None = None
    errors: list[ErrorDetail] = []
    metadata: dict[str, str | int | float] = {}

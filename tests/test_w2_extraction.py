from unittest.mock import AsyncMock, patch

from baml_client.types import (
    DeductionLineItem,
    DocumentType,
    EarningsLineItem,
    IncomePeriod,
    PayFrequency,
    TaxWithholding,
    W2EarningsExtraction,
)
from baml_py.baml_py import BamlClientError

from tests.conftest import MINIMAL_PNG

CLASSIFY_TARGET = "app.services.graph.b.ClassifyDocument"
EXTRACT_TARGET = "app.services.graph.b.ExtractW2Earnings"


def _make_w2(**overrides) -> W2EarningsExtraction:
    defaults = dict(
        employer_name="Greenfield Property Management LLC",
        employer_ein="74-3928156",
        employer_address="1450 Market Street, Suite 300, San Francisco, CA 94103",
        employee_name="Maria Santos Rodriguez",
        employee_ssn="***-**-8842",
        employee_address="742 Evergreen Terrace, Apt 4B, Oakland, CA 94612",
        employee_id="EMP-20847",
        department="Leasing Operations",
        wages_tips_compensation=67450.0,
        social_security_wages=67450.0,
        medicare_wages=67450.0,
        tax_withholding=TaxWithholding(
            federal_income_tax=9843.75,
            social_security_tax=4181.90,
            medicare_tax=977.03,
            state_income_tax=3104.70,
        ),
        retirement_plan=True,
        box_12_codes=["D - 401(k): 4500.00"],
        control_number="A2025-00847",
        allocated_tips=0.0,
        dependent_care=0.0,
        state="CA",
        state_id="800-555-1234",
        state_wages=67450.0,
        state_tax=3104.70,
        pay_period=IncomePeriod(start_date="2025-01-01", end_date="2025-01-15"),
        pay_date="2025-01-17",
        pay_frequency=PayFrequency.BiWeekly,
        earnings=[
            EarningsLineItem(description="Regular Salary", hours=80.0, rate=32.43, current_amount=2594.23, ytd_amount=2594.23),
            EarningsLineItem(description="Overtime", hours=4.5, rate=48.65, current_amount=218.91, ytd_amount=218.91),
        ],
        deductions=[
            DeductionLineItem(description="Federal Income Tax", current_amount=410.94, ytd_amount=410.94),
            DeductionLineItem(description="Health Insurance - Employee", current_amount=125.00, ytd_amount=125.00),
        ],
        gross_pay=2813.14,
        net_pay=1763.58,
        tax_year=2025,
        document_type="w2_earnings",
        currency="USD",
        confidence_notes=[],
    )
    defaults.update(overrides)
    return W2EarningsExtraction(**defaults)  # type: ignore[arg-type]


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_returns_success_when_all_fields_present(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2()
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.status == "success"
    assert resp.errors == []
    assert resp.data is not None
    assert resp.data.extraction_type == "w2_earnings"
    assert resp.data.employer_name == "Greenfield Property Management LLC"
    assert resp.data.wages_tips_compensation == 67450.0
    assert resp.data.employee_ssn == "***-**-8842"


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_returns_partial_when_employer_missing(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2(employer_name=None)
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.status == "partial"
    assert any(e.field == "employer_name" and e.error_type == "missing_field" for e in resp.errors)


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_returns_partial_when_wages_missing(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2(wages_tips_compensation=None)
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.status == "partial"
    assert any(e.field == "wages_tips_compensation" and e.error_type == "missing_field" for e in resp.errors)


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_returns_partial_when_employee_name_missing(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2(employee_name=None)
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.status == "partial"
    assert any(e.field == "employee_name" and e.error_type == "missing_field" for e in resp.errors)


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_returns_error_on_baml_exception(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.side_effect = BamlClientError("fail")
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.status == "error"
    assert resp.data is None
    assert resp.errors[0].error_type == "extraction_failed"


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_negative_wages_is_validation_error(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2(wages_tips_compensation=-5000.0)
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.status == "partial"
    error = next(e for e in resp.errors if e.field == "wages_tips_compensation")
    assert error.error_type == "validation_error"
    assert error.raw_value == "-5000.0"


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_negative_gross_pay_is_validation_error(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2(gross_pay=-100.0)
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.status == "partial"
    error = next(e for e in resp.errors if e.field == "gross_pay")
    assert error.error_type == "validation_error"


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_processing_time_is_populated(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2()
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert "processing_time_ms" in resp.metadata
    processing_time = resp.metadata["processing_time_ms"]
    assert isinstance(processing_time, (int, float)) and processing_time >= 0


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_tax_withholding_populated(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2()
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.data is not None
    assert resp.data.tax_withholding is not None
    assert resp.data.tax_withholding.federal_income_tax == 9843.75
    assert resp.data.tax_withholding.social_security_tax == 4181.90
    assert resp.data.tax_withholding.medicare_tax == 977.03


@patch(EXTRACT_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_earnings_and_deductions_populated(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = _make_w2()
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.data is not None
    assert len(resp.data.earnings) == 2
    assert resp.data.earnings[0].description == "Regular Salary"
    assert resp.data.earnings[0].hours == 80.0
    assert len(resp.data.deductions) == 2
    assert resp.data.deductions[0].description == "Federal Income Tax"

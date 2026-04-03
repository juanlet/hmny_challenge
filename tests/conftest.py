import pytest
from httpx import ASGITransport, AsyncClient

from baml_client.types import (
    DeductionLineItem,
    EarningsLineItem,
    IncomeExtraction,
    IncomePeriod,
    PayFrequency,
    TaxWithholding,
    W2EarningsExtraction,
)
from app.main import app

# Valid 1×1 transparent PNG (68 bytes)
MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6260000000020001e221bc330000000049454e44ae426082"
)

# Minimal valid PDF
MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n109\n%%EOF\n"


@pytest.fixture
def minimal_png_bytes() -> bytes:
    return MINIMAL_PNG


@pytest.fixture
def minimal_pdf_bytes() -> bytes:
    return MINIMAL_PDF


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
def mock_baml_success() -> IncomeExtraction:
    return IncomeExtraction(
        employer_name="Acme Corp",
        employee_name="Jane Doe",
        gross_income=5000.0,
        net_income=3800.0,
        pay_frequency=PayFrequency.BiWeekly,
        income_period=IncomePeriod(start_date="2024-01-01", end_date="2024-01-14"),
        document_type="pay_stub",
        currency="USD",
        confidence_notes=[],
    )


@pytest.fixture
def mock_baml_missing_fields() -> IncomeExtraction:
    return IncomeExtraction(
        employer_name=None,
        employee_name="Jane Doe",
        gross_income=None,
        net_income=3800.0,
        pay_frequency=PayFrequency.BiWeekly,
        income_period=IncomePeriod(start_date="2024-01-01", end_date="2024-01-14"),
        document_type="pay_stub",
        currency="USD",
        confidence_notes=[],
    )


# ---------------------------------------------------------------------------
# W2 / Earnings Statement fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_w2_success() -> W2EarningsExtraction:
    return W2EarningsExtraction(
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
            DeductionLineItem(description="Social Security (6.2%)", current_amount=174.41, ytd_amount=174.41),
            DeductionLineItem(description="Medicare (1.45%)", current_amount=40.79, ytd_amount=40.79),
            DeductionLineItem(description="CA State Income Tax", current_amount=129.63, ytd_amount=129.63),
            DeductionLineItem(description="401(k) Contribution (6%)", current_amount=168.79, ytd_amount=168.79),
            DeductionLineItem(description="Health Insurance - Employee", current_amount=125.00, ytd_amount=125.00),
        ],
        gross_pay=2813.14,
        net_pay=1763.58,
        tax_year=2025,
        document_type="w2_earnings",
        currency="USD",
        confidence_notes=[],
    )


@pytest.fixture
def mock_w2_missing_fields() -> W2EarningsExtraction:
    return W2EarningsExtraction(
        employer_name=None,
        employer_ein=None,
        employer_address=None,
        employee_name=None,
        employee_ssn=None,
        employee_address=None,
        employee_id=None,
        department=None,
        wages_tips_compensation=None,
        social_security_wages=None,
        medicare_wages=None,
        tax_withholding=None,
        retirement_plan=None,
        box_12_codes=[],
        control_number=None,
        allocated_tips=None,
        dependent_care=None,
        state=None,
        state_id=None,
        state_wages=None,
        state_tax=None,
        pay_period=None,
        pay_date=None,
        pay_frequency=None,
        earnings=[],
        deductions=[],
        gross_pay=None,
        net_pay=None,
        tax_year=None,
        document_type=None,
        currency=None,
        confidence_notes=[],
    )

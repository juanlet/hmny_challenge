import pytest
from httpx import ASGITransport, AsyncClient

from baml_client.types import IncomeExtraction, IncomePeriod, PayFrequency
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

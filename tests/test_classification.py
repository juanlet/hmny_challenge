from unittest.mock import AsyncMock, patch

from baml_client.types import DocumentType, IncomeExtraction, IncomePeriod, PayFrequency
from baml_py.baml_py import BamlClientError

from tests.conftest import MINIMAL_PNG

CLASSIFY_TARGET = "app.services.graph.b.ClassifyDocument"
EXTRACT_INCOME_TARGET = "app.services.graph.b.ExtractIncome"
EXTRACT_W2_TARGET = "app.services.graph.b.ExtractW2Earnings"


def _make_income(**overrides) -> IncomeExtraction:
    defaults = dict(
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
    defaults.update(overrides)
    return IncomeExtraction(**defaults)  # type: ignore[arg-type]


@patch(EXTRACT_INCOME_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_income_classification_routes_to_income_extractor(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.Income
    mock_extract.return_value = _make_income()
    resp = await run_extraction(MINIMAL_PNG, "stub.png")
    assert resp.status == "success"
    assert resp.data is not None
    assert resp.data.extraction_type == "income"
    mock_extract.assert_called_once()


@patch(EXTRACT_INCOME_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_classification_failure_defaults_to_income(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.side_effect = BamlClientError("classification failed")
    mock_extract.return_value = _make_income()
    resp = await run_extraction(MINIMAL_PNG, "stub.png")
    assert resp.status == "success"
    assert resp.data is not None
    assert resp.data.extraction_type == "income"
    mock_extract.assert_called_once()


@patch(EXTRACT_W2_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_w2_classification_routes_to_w2_extractor(mock_classify, mock_extract):
    from app.services.graph import run_extraction
    from tests.conftest import MINIMAL_PNG
    from baml_client.types import W2EarningsExtraction, TaxWithholding

    mock_classify.return_value = DocumentType.W2Earnings
    mock_extract.return_value = W2EarningsExtraction(
        employer_name="Test Corp",
        employee_name="John Doe",
        wages_tips_compensation=50000.0,
        box_12_codes=[],
        earnings=[],
        deductions=[],
        confidence_notes=[],
    )
    resp = await run_extraction(MINIMAL_PNG, "w2.png")
    assert resp.status == "success"
    assert resp.data is not None
    assert resp.data.extraction_type == "w2_earnings"
    mock_extract.assert_called_once()

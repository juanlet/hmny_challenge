from unittest.mock import AsyncMock, patch

from baml_client.types import DocumentType, IncomeExtraction, IncomePeriod, PayFrequency
from baml_py.baml_py import BamlClientError

from tests.conftest import MINIMAL_PNG

PATCH_TARGET = "app.services.graph.b.ExtractIncome"
CLASSIFY_TARGET = "app.services.graph.b.ClassifyDocument"


def _make_extraction(**overrides) -> IncomeExtraction:
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


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_returns_success_when_all_fields_present(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.Income
    mock_extract.return_value = _make_extraction()
    resp = await run_extraction(MINIMAL_PNG, "stub.png")
    assert resp.status == "success"
    assert resp.errors == []
    assert resp.data is not None
    assert resp.data.employer_name == "Acme Corp"


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_returns_partial_when_pay_frequency_missing(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.Income
    mock_extract.return_value = _make_extraction(pay_frequency=None)
    resp = await run_extraction(MINIMAL_PNG, "stub.png")
    assert resp.status == "partial"
    assert len(resp.errors) == 1
    assert resp.errors[0].field == "pay_frequency"
    assert resp.errors[0].error_type == "missing_field"


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_returns_error_on_baml_exception(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.Income
    mock_extract.side_effect = BamlClientError("fail")
    resp = await run_extraction(MINIMAL_PNG, "stub.png")
    assert resp.status == "error"
    assert resp.data is None
    assert resp.errors[0].error_type == "extraction_failed"


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_negative_gross_income_is_validation_error(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.Income
    mock_extract.return_value = _make_extraction(gross_income=-100.0)
    resp = await run_extraction(MINIMAL_PNG, "stub.png")
    assert resp.status == "partial"
    error = next(e for e in resp.errors if e.field == "gross_income")
    assert error.error_type == "validation_error"
    assert error.raw_value == "-100.0"


@patch(PATCH_TARGET, new_callable=AsyncMock)
@patch(CLASSIFY_TARGET, new_callable=AsyncMock)
async def test_processing_time_is_populated(mock_classify, mock_extract):
    from app.services.graph import run_extraction

    mock_classify.return_value = DocumentType.Income
    mock_extract.return_value = _make_extraction()
    resp = await run_extraction(MINIMAL_PNG, "stub.png")
    assert "processing_time_ms" in resp.metadata
    processing_time = resp.metadata["processing_time_ms"]
    assert isinstance(processing_time, (int, float)) and processing_time >= 0

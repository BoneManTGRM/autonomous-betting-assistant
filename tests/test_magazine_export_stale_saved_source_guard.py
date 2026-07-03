from autonomous_betting_agent.magazine_export_state_guard import (
    _is_stale_saved_export_row,
    _select_rows,
    _valid_rows,
)


def test_saved_uploaded_verify_price_rows_are_invalid_for_magazine_export():
    row = {
        "event": "Seattle Storm at Phoenix Mercury",
        "prediction": "Spread: Phoenix Mercury -1.5",
        "report_source": "Uploaded / saved row",
        "data_scope": "Price verification required",
        "truth": "VERIFY PRICE",
        "odds_status": "UPLOADED_ROW",
        "preview_summary": "Saved handoff rows are being used. Confirm this is the newest run before publishing.",
        "decimal_price": 1.65,
        "model_probability": 0.62,
        "model_market_edge": 0.011,
        "expected_value_per_unit": 0.017,
    }

    assert _is_stale_saved_export_row(row)
    assert _valid_rows([row]) == []


def test_locked_saved_rows_are_allowed_for_magazine_export():
    row = {
        "event": "Seattle Storm at Phoenix Mercury",
        "prediction": "Spread: Phoenix Mercury -1.5",
        "report_source": "Uploaded / saved row",
        "truth": "VERIFY PRICE",
        "odds_status": "UPLOADED_ROW",
        "proof_id": "OLP-123",
        "locked_at_utc": "2026-07-03T12:00:00Z",
        "decimal_price": 1.65,
        "model_probability": 0.62,
        "model_market_edge": 0.011,
    }

    assert not _is_stale_saved_export_row(row)
    assert len(_valid_rows([row])) == 1


def test_export_selection_returns_no_rows_when_only_stale_saved_rows_exist():
    stale = {
        "event": "San Diego Padres at Los Angeles Dodgers",
        "prediction": "Run Line: San Diego Padres +1.5",
        "report_source": "Uploaded / saved row",
        "data_scope": "Price verification required",
        "truth": "VERIFY PRICE",
        "odds_status": "UPLOADED_ROW",
        "preview_summary": "Saved handoff rows are being used. Confirm this is the newest run before publishing.",
        "decimal_price": 1.78,
        "model_probability": 0.58,
        "model_market_edge": 0.022,
    }

    rows, recovered, _sig = _select_rows([stale], report_name="test", language="en", source="pdf-export")

    assert rows == []
    assert recovered is False

from autonomous_betting_agent.report_source_quality_guard import (
    best_source_key,
    row_is_stale_saved_handoff,
    source_quality_score,
    usable_report_rows,
)


def test_uploaded_saved_verify_price_row_is_stale():
    row = {
        "event": "Seattle Storm at Phoenix Mercury",
        "report_source": "Uploaded / saved row",
        "data_scope": "Saved-source verification report",
        "truth": "VERIFY PRICE",
        "odds_status": "UPLOADED_ROW",
        "model_probability_clean": 0.62,
        "decimal_price": 1.65,
        "model_market_edge": 0.011,
    }

    assert row_is_stale_saved_handoff(row)
    assert usable_report_rows([row]) == []
    assert source_quality_score("pro_predictor_high_confidence_rows", [row])[0] == 0


def test_locked_proof_row_is_not_stale_even_if_saved_source_text_exists():
    row = {
        "event": "Seattle Storm at Phoenix Mercury",
        "report_source": "Uploaded / saved row",
        "truth": "VERIFY PRICE",
        "odds_status": "UPLOADED_ROW",
        "proof_id": "OLP-123",
        "locked_at_utc": "2026-07-03T12:00:00Z",
        "model_probability_clean": 0.62,
        "decimal_price": 1.65,
        "model_market_edge": 0.011,
    }

    assert not row_is_stale_saved_handoff(row)
    assert source_quality_score("odds_lock_pro_locked_rows", [row])[0] == 1


def test_best_source_ignores_stale_saved_candidate_for_live_candidate():
    stale = {
        "report_source": "Uploaded / saved row",
        "truth": "VERIFY PRICE",
        "odds_status": "UPLOADED_ROW",
        "model_probability_clean": 0.62,
        "decimal_price": 1.65,
        "model_market_edge": 0.011,
    }
    live = {
        "report_source": "Current run / session rows",
        "verification_status": "LIVE VERIFIED",
        "model_probability_clean": 0.58,
        "decimal_price": 1.91,
        "model_market_edge": 0.03,
    }

    assert best_source_key([
        ("pro_predictor_high_confidence_rows", [stale]),
        ("pro_predictor_latest_rows", [live]),
    ]) == "pro_predictor_latest_rows"

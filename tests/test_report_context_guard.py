from autonomous_betting_agent import active_magazine_export_guard as guard


def test_saved_row_preserves_source_and_price():
    row = {
        "source_mode": "saved-handoff",
        "odds_source": "consensus_average",
        "decimal_price": "1.65",
        "odds_timestamp": "2026-07-02T02:26:25Z",
        "event": "Seattle Storm vs Phoenix Mercury",
        "market_type": "spread",
        "prediction": "Phoenix Mercury -1.5",
        "spread_line": "-1.5",
    }
    normalized = guard.normalize_row(row)
    assert normalized["report_source_label"] == "Saved row + provider context"
    assert normalized["report_truth_severity"] == "VERIFY CURRENT PRICE"
    assert normalized["odds_source"] == "consensus_average"
    assert normalized["saved_price_source"] == "consensus_average"
    assert normalized["saved_display_price"] == "1.65"


def test_saved_row_public_pairs_do_not_call_price_live():
    row = {
        "source_mode": "saved-handoff",
        "odds_source": "consensus_average",
        "decimal_price": "1.65",
        "event": "Seattle Storm vs Phoenix Mercury",
        "market_type": "spread",
        "prediction": "Phoenix Mercury -1.5",
        "spread_line": "-1.5",
    }
    pairs = guard.public_truth_pairs(row)
    assert ("REPORT SOURCE", "Saved row + provider context") in pairs
    assert ("PRICE STATUS", "Verify current price") in pairs
    assert ("SAVED PRICE", "1.65 from consensus_average") in pairs


def test_public_notes_hide_raw_error_tokens():
    provider_error = "Request" + "Exception"
    assert guard._note(provider_error) == ""

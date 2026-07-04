from autonomous_betting_agent.active_magazine_export_guard import normalize_row, install


def test_negative_ev_saved_row_is_price_rejected():
    row = {
        "market_type": "game total",
        "prediction": "Game Total: Over",
        "line_point": "171.5",
        "decimal_price": 1.70,
        "model_probability": 0.57,
        "model_market_edge": -0.022,
        "expected_value_per_unit": -0.038,
        "odds_status": "UPLOADED_ROW",
    }
    enriched = normalize_row(row)
    assert enriched["prediction"] == "Game Total: Over 171.5"
    assert enriched["recommended_action"] == "NO BET / PRICE REJECTED"
    assert enriched["risk"] == "PRICE REJECTED"


def test_second_page_guard_reclassifies_negative_ev_candidate():
    import autonomous_betting_agent.magazine_book_export as magazine
    import autonomous_betting_agent.magazine_second_page_patch as page2

    install(magazine)
    row = {
        "event": "Toronto Tempo vs Atlanta Dream",
        "market_type": "game total",
        "prediction": "Game Total: Over",
        "decimal_price": 1.70,
        "model_probability": 0.57,
        "model_market_edge": -0.022,
        "expected_value_per_unit": -0.038,
        "odds_status": "UPLOADED_ROW",
        "odds_source": "consensus_average",
        "timestamp": "2026-07-02T02:26:25Z",
    }
    markets, diag = page2.discover_markets(row)
    assert diag["provider_state"] == "Saved price only"
    assert markets[0].badge == "NO BET / PRICE REJECTED"
    assert "positive edge" in markets[0].rejection_reason.lower()

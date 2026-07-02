from autonomous_betting_agent.magazine_regression_guard import _enrich_pick, install
from autonomous_betting_agent.report_public_quality import (
    build_full_market_label,
    provider_state,
    public_action_label,
    public_recommendation_status,
)


def test_spread_line_is_recovered_from_prediction_text():
    row = {"market_type": "spread", "prediction": "Point Spread: Phoenix Mercury -1.5"}
    assert build_full_market_label(row) == "Spread: Phoenix Mercury -1.5"


def test_run_line_is_recovered_from_prediction_text():
    row = {"market_type": "run line", "prediction": "Point Spread: San Diego Padres +1.5"}
    assert build_full_market_label(row) == "Run Line: San Diego Padres +1.5"


def test_total_line_is_recovered_only_when_present_in_text():
    assert build_full_market_label({"market_type": "game total", "prediction": "Game Total: Over 171.5"}) == "Game Total: Over 171.5"
    assert "Missing exact market line" in build_full_market_label({"market_type": "game total", "prediction": "Game Total: Over"})


def test_negative_ev_and_edge_are_no_bet_not_watchlist_even_saved_source():
    row = {
        "market_type": "game total",
        "prediction": "Game Total: Over",
        "decimal_price": 1.70,
        "model_probability": 0.57,
        "model_market_edge": -0.022,
        "expected_value_per_unit": -0.038,
        "odds_status": "UPLOADED_ROW",
        "odds_source": "consensus_average",
    }
    status = public_recommendation_status(row)
    assert "No bet" in status
    assert public_action_label(row) == "NO BET / PRICE REJECTED"
    assert "Watchlist" not in status


def test_saved_source_never_reports_provider_matched():
    row = {"odds_status": "UPLOADED_ROW", "odds_source": "consensus_average"}
    assert provider_state(row) == "Source saved"


def test_magazine_enrichment_rewrites_page_one_action_and_label():
    row = {
        "market_type": "spread",
        "prediction": "Point Spread: Las Vegas Aces +1.5",
        "decimal_price": 1.65,
        "model_probability": 0.58,
        "model_market_edge": -0.024,
        "expected_value_per_unit": -0.039,
        "recommended_action": "WATCHLIST",
        "odds_status": "UPLOADED_ROW",
    }
    enriched = _enrich_pick(row)
    assert enriched["prediction"] == "Spread: Las Vegas Aces +1.5"
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
    assert diag["provider_state"] == "Source saved"
    assert markets[0].badge == "NO BET / PRICE REJECTED"
    assert "positive edge" in markets[0].rejection_reason.lower()

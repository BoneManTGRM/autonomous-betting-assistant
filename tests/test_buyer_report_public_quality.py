from autonomous_betting_agent.magazine_second_page_patch import _page_two_sections
from autonomous_betting_agent.report_public_quality import (
    LIVE_TRIGGER_UNAVAILABLE,
    MISSING_EXACT_MARKET_LINE,
    NO_VERIFIED_PARLAY,
    build_full_market_label,
    public_diagnostic_banned_terms,
    public_recommendation_status,
    sanitize_public_text,
    trim_complete_sentence,
)


def _flat(sections):
    return "\n".join(item for _title, rows, _color in sections for item in rows)


def test_full_market_labels_include_exact_lines():
    assert build_full_market_label({"market_type": "game total", "selection": "Over", "total_line": 171.5}) == "Game Total: Over 171.5"
    assert build_full_market_label({"market_type": "totals", "prediction": "Under", "line": "184.5"}) == "Game Total: Under 184.5"
    assert build_full_market_label({"market_type": "spread", "selection": "Phoenix Mercury", "spread_line": -1.5}) == "Spread: Phoenix Mercury -1.5"
    assert build_full_market_label({"market_type": "run line", "selection": "San Diego Padres", "run_line": 1.5}) == "Run Line: San Diego Padres +1.5"
    assert build_full_market_label({"market_type": "moneyline", "selection": "Philadelphia Phillies"}) == "Moneyline: Philadelphia Phillies"


def test_missing_line_and_negative_value_are_publicly_clear():
    label = build_full_market_label({"market_type": "game total", "selection": "Over"})
    assert MISSING_EXACT_MARKET_LINE in label
    assert label != "Over"
    status = public_recommendation_status({
        "market_type": "moneyline",
        "selection": "Team A",
        "decimal_price": 2.0,
        "model_probability": 0.45,
        "model_market_edge": -0.05,
        "expected_value_per_unit": -0.10,
        "odds_source": "The Odds API",
    })
    assert "No bet" in status
    assert "Watchlist" not in status


def test_public_text_removes_raw_diagnostics_and_dangling_fragments():
    text = sanitize_public_text("Gate failed - endpoint unknown - status code unknown - rows returned: 1 - UPLOADED_ROW")
    for banned in public_diagnostic_banned_terms():
        assert banned.lower() not in text.lower()
    assert "Verification pending" in text
    assert trim_complete_sentence("The matchup context is available. This sentence ends where the") == "The matchup context is available."


def test_page_two_sections_are_buyer_facing_and_exact():
    row = {
        "event": "A vs B",
        "sport": "basketball",
        "market_type": "game total",
        "selection": "Over",
        "total_line": 171.5,
        "decimal_price": 1.91,
        "model_probability": 0.60,
        "odds_source": "The Odds API",
        "sportsbook": "Book A",
        "timestamp": "2026-07-02T04:00:00Z",
        "provider_event_id": "evt-1",
        "expected_value_per_unit": 0.146,
        "model_market_edge": 0.076,
    }
    rendered = _flat(_page_two_sections(row, "en"))
    assert "Game Total: Over 171.5" in rendered
    assert NO_VERIFIED_PARLAY in rendered
    assert LIVE_TRIGGER_UNAVAILABLE in rendered
    assert "Gate failed" not in rendered
    assert "endpoint" not in rendered.lower()
    assert "status code" not in rendered.lower()
    assert "rows returned" not in rendered.lower()

import json

import pandas as pd

from autonomous_betting_agent.dashboard_data_service import build_dashboard_data
from autonomous_betting_agent.dashboard_ui import (
    assert_no_demo_dashboard_values,
    dashboard_json_text,
    dashboard_tables,
    missing_dashboard_fields,
    status_cards,
)


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event": "Alpha vs Beta",
                "prediction": "Alpha ML",
                "market_type": "h2h",
                "bookmaker": "Book A",
                "decimal_odds": 2.10,
                "model_probability": 0.61,
                "market_probability": 0.51,
                "no_vig_implied_probability": 0.53,
                "expected_value_per_unit": 0.281,
                "model_market_edge": 0.10,
                "manual_clv": 0.04,
                "stake_units": 1.0,
                "result": "win",
                "official_publish_ready": True,
                "odds_verified": True,
                "proof_id": "proof-alpha",
                "locked_at_utc": "2026-06-29T10:00:00Z",
                "event_start_utc": "2026-06-29T19:00:00Z",
            },
            {
                "event": "Gamma vs Delta",
                "prediction": "Gamma spread",
                "market_type": "spreads",
                "bookmaker": "Book B",
                "decimal_odds": 1.95,
                "model_probability": 0.55,
                "market_probability": 0.52,
                "expected_value_per_unit": 0.0725,
                "model_market_edge": 0.03,
                "stake_units": 1.0,
                "result": "loss",
                "report_lane": "watchlist",
                "odds_verified": True,
            },
            {
                "event": "Epsilon vs Zeta",
                "prediction": "Epsilon total",
                "market_type": "totals",
                "bookmaker": "Book C",
                "decimal_odds": 1.80,
                "model_probability": 0.49,
                "market_probability": 0.57,
                "expected_value_per_unit": -0.118,
                "model_market_edge": -0.08,
                "stake_units": 1.0,
                "result": "cancel",
                "data_issue_reason": "negative edge",
                "odds_verified": True,
            },
        ]
    )


def _dashboard() -> dict:
    return build_dashboard_data(
        _rows(),
        learning_rows=pd.DataFrame([{"row": "learn-a"}]),
        api_usage={"used_calls": 321, "call_limit": 1000, "sources": ["test-source"]},
        bankroll=500,
        unit_size=10,
        generated_at="fixed-time",
    )


def test_dashboard_ui_status_cards_with_complete_real_data():
    dashboard = _dashboard()
    cards = status_cards(dashboard)

    labels = {card["label"]: card["value"] for card in cards}
    assert labels["Events Scanned"] == "3"
    assert labels["Positive EV Picks"] == "1"
    assert labels["Watchlist Picks"] == "1"
    assert labels["Avoid Picks"] == "1"
    assert labels["Best Edge Today"] == "+10.0%"
    assert labels["Model Status"] == "Stable"
    assert labels["Drift Status"] == "No Drift"
    assert labels["Learning Rows"] == "1"
    assert labels["Bankroll Risk"] == "Low"
    assert labels["API Usage"] == "32.1%"


def test_dashboard_ui_empty_missing_data_safety_path():
    dashboard = build_dashboard_data(pd.DataFrame())
    cards = status_cards(dashboard)
    tables = dashboard_tables(dashboard)

    assert {card["key"]: card["value"] for card in cards}["events_scanned"] == "0"
    assert {card["key"]: card["value"] for card in cards}["best_edge_today"] == "N/A"
    assert tables["top_positive_ev_picks"].empty
    assert tables["recent_activity"].shape[0] >= 2
    assert missing_dashboard_fields(dashboard, ["events_scanned", "roi_summary", "api_usage"]) == []


def test_dashboard_ui_top_picks_table_formatting():
    tables = dashboard_tables(_dashboard())
    top = tables["top_positive_ev_picks"]

    assert not top.empty
    assert list(top.columns[:6]) == ["event", "market", "pick", "book", "odds", "model_probability"]
    assert top.iloc[0]["event"] == "Alpha vs Beta"
    assert top.iloc[0]["status"] == "PLAYABLE"


def test_dashboard_ui_json_contract_availability():
    dashboard = _dashboard()
    json_text = dashboard_json_text(dashboard)
    parsed = json.loads(json_text)

    assert parsed["events_scanned"] == 3
    assert parsed["positive_ev_picks"] == 1
    assert parsed["api_usage"]["usage_display"] == "32.1%"
    assert parsed["roi_summary"]["wins"] == 1
    assert "top_positive_ev_picks" in parsed
    assert "odds_lock_summary" in parsed


def test_dashboard_ui_has_no_design_mock_dashboard_values():
    dashboard = _dashboard()
    payload = dashboard_json_text(dashboard)

    assert assert_no_demo_dashboard_values(dashboard)
    assert "Alpha vs Beta" in payload
    assert "John Doe" not in payload
    assert "NY Liberty -120" not in payload
    assert "+8.4%" not in payload

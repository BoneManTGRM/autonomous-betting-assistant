import pandas as pd

from autonomous_betting_agent.dashboard_data_service import DASHBOARD_FIELDS, build_dashboard_data


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event": "Aces vs Liberty",
                "prediction": "Aces ML",
                "market_type": "h2h",
                "bookmaker": "Caliente",
                "decimal_odds": 1.90,
                "model_probability": 0.64,
                "market_probability": 0.58,
                "no_vig_implied_probability": 0.59,
                "expected_value_per_unit": 0.216,
                "model_market_edge": 0.06,
                "manual_clv": 0.03,
                "stake_units": 1.0,
                "result": "win",
                "official_publish_ready": True,
                "odds_verified": True,
                "proof_id": "proof-1",
                "locked_at_utc": "2026-06-29T10:00:00Z",
                "event_start_utc": "2026-06-29T19:00:00Z",
            },
            {
                "event": "Red Sox vs Yankees",
                "prediction": "Red Sox RL",
                "market_type": "spreads",
                "bookmaker": "DraftKings",
                "decimal_odds": 2.05,
                "model_probability": 0.54,
                "market_probability": 0.49,
                "no_vig_implied_probability": 0.50,
                "expected_value_per_unit": 0.107,
                "model_market_edge": 0.05,
                "manual_clv": -0.01,
                "stake_units": 1.0,
                "result": "loss",
                "official_publish_ready": True,
                "odds_verified": True,
                "proof_id": "proof-2",
                "locked_at_utc": "2026-06-29T10:10:00Z",
                "event_start_utc": "2026-06-29T19:10:00Z",
            },
            {
                "event": "Carlos Alcaraz vs D Medvedev",
                "prediction": "Alcaraz ML",
                "market_type": "h2h",
                "bookmaker": "Bet365",
                "decimal_odds": 1.67,
                "model_probability": 0.62,
                "market_probability": 0.60,
                "expected_value_per_unit": 0.035,
                "model_market_edge": 0.02,
                "stake_units": 1.0,
                "result": "push",
                "report_lane": "watchlist",
                "odds_verified": True,
                "event_start_utc": "2026-06-29T19:30:00Z",
            },
            {
                "event": "Dodgers vs Giants",
                "prediction": "Dodgers ML",
                "market_type": "h2h",
                "bookmaker": "BetMGM",
                "decimal_odds": 1.74,
                "model_probability": 0.50,
                "market_probability": 0.57,
                "expected_value_per_unit": -0.13,
                "model_market_edge": -0.07,
                "stake_units": 1.0,
                "result": "cancel",
                "data_issue_reason": "negative edge",
                "odds_verified": True,
                "event_start_utc": "2026-06-29T20:00:00Z",
            },
        ]
    )


def test_dashboard_json_shape_and_required_fields():
    dashboard = build_dashboard_data(
        _rows(),
        learning_rows=pd.DataFrame([{"row": 1}, {"row": 2}]),
        api_usage={"used_calls": 12420, "call_limit": 20000, "sources": ["odds", "sportsdataio"]},
        bankroll=1000,
        unit_size=10,
        generated_at="2026-06-29 11:30 UTC",
    )

    for field in DASHBOARD_FIELDS:
        assert field in dashboard
    assert dashboard["events_scanned"] == 4
    assert dashboard["positive_ev_picks"] == 2
    assert dashboard["watchlist_picks"] == 1
    assert dashboard["avoid_picks"] == 1
    assert dashboard["learning_rows_scanned"] == 2
    assert dashboard["model_status"] == "Stable"
    assert dashboard["drift_status"] == "No Drift"
    assert dashboard["bankroll_risk"] == "Low"
    assert dashboard["api_usage"]["usage_fraction"] == 0.621
    assert dashboard["api_usage"]["usage_display"] == "62.1%"


def test_dashboard_top_picks_best_edge_odds_lock_and_bankroll_summary():
    dashboard = build_dashboard_data(_rows(), bankroll=1000, unit_size=10)

    assert dashboard["top_positive_ev_picks"][0]["event"] == "Aces vs Liberty"
    assert dashboard["best_edge_today"]["edge_display"] == "+6.0%"
    assert dashboard["odds_lock_summary"]["status"] == "PLAYABLE"
    assert dashboard["odds_lock_summary"]["best_value_now"] == "Aces vs Liberty"
    assert dashboard["bankroll_summary"]["recommended_bets"] == 2
    assert dashboard["bankroll_summary"]["total_units_risked"] == 2
    assert dashboard["bankroll_summary"]["daily_exposure"] == 20
    assert dashboard["bankroll_summary"]["risk_level"] == "Low"


def test_dashboard_proof_clv_roi_activity_and_upcoming_events():
    dashboard = build_dashboard_data(_rows(), bankroll=1000, unit_size=10, generated_at="fixed")

    assert dashboard["proof_summary"]["proof_rows"] == 2
    assert dashboard["proof_summary"]["locked_rows"] == 2
    assert dashboard["proof_summary"]["verified_odds_rows"] == 4
    assert dashboard["clv_summary"]["count"] == 2
    assert dashboard["clv_summary"]["average_clv_display"] == "+1.0%"
    assert dashboard["roi_summary"]["wins"] == 1
    assert dashboard["roi_summary"]["losses"] == 1
    assert dashboard["roi_summary"]["pushes"] == 1
    assert dashboard["roi_summary"]["cancels"] == 1
    assert dashboard["roi_summary"]["win_rate_display"] == "50.0%"
    assert dashboard["recent_activity"][0]["timestamp"] == "fixed"
    assert len(dashboard["upcoming_events"]) == 4


def test_dashboard_empty_missing_data_safety_path():
    dashboard = build_dashboard_data(pd.DataFrame())

    for field in DASHBOARD_FIELDS:
        assert field in dashboard
    assert dashboard["events_scanned"] == 0
    assert dashboard["positive_ev_picks"] == 0
    assert dashboard["watchlist_picks"] == 0
    assert dashboard["avoid_picks"] == 0
    assert dashboard["best_edge_today"]["edge_display"] == "N/A"
    assert dashboard["model_status"] == "Needs Data"
    assert dashboard["drift_status"] == "No Data"
    assert dashboard["bankroll_risk"] == "Low"
    assert dashboard["api_usage"]["usage_fraction"] == 0.0
    assert dashboard["top_positive_ev_picks"] == []
    assert dashboard["odds_lock_summary"]["status"] == "NO_PLAYABLE_LOCK"
    assert dashboard["roi_summary"]["total_picks"] == 0

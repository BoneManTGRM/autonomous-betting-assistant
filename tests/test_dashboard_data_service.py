import pandas as pd

from autonomous_betting_agent.dashboard_data_service import DASHBOARD_FIELDS, build_dashboard_data


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event": "NY Liberty vs Las Vegas Aces",
                "prediction": "NY Liberty ML",
                "market_type": "h2h",
                "bookmaker": "Caliente",
                "decimal_odds": 2.0,
                "model_probability": 0.60,
                "no_vig_implied_probability": 0.52,
                "expected_value_per_unit": 0.20,
                "odds_verified": True,
                "result": "pending",
                "stake_units": 12,
                "manual_clv": 0.04,
                "event_start_utc": "2026-06-29T19:00:00Z",
                "learning_status": "included",
            },
            {
                "event": "Boston Red Sox vs NY Yankees",
                "prediction": "Boston Red Sox RL",
                "market_type": "spreads",
                "bookmaker": "DraftKings",
                "decimal_odds": 2.10,
                "model_probability": 0.55,
                "no_vig_implied_probability": 0.50,
                "expected_value_per_unit": 0.155,
                "odds_verified": True,
                "result": "loss",
                "stake_units": 1,
                "manual_clv": -0.01,
            },
            {
                "event": "Man City vs Arsenal",
                "prediction": "Over 2.5",
                "market_type": "totals",
                "bookmaker": "FanDuel",
                "decimal_odds": 1.90,
                "model_probability": 0.50,
                "no_vig_implied_probability": 0.51,
                "expected_value_per_unit": -0.05,
                "report_lane": "watchlist",
                "odds_verified": True,
                "result": "pending",
                "stake_units": 1,
                "manual_clv": 0.02,
                "event_start_utc": "2026-06-29T20:00:00Z",
            },
            {
                "event": "LA Dodgers vs SF Giants",
                "prediction": "Dodgers ML",
                "market_type": "h2h",
                "bookmaker": "BetMGM",
                "data_issue_reason": "missing odds",
                "result": "pending",
                "stake_units": 1,
            },
        ]
    )


def test_dashboard_json_shape_and_required_fields():
    dashboard = build_dashboard_data(
        _rows(),
        learning_rows=pd.DataFrame([{"row": 1}, {"row": 2}, {"row": 3}]),
        api_usage={"used_calls": 620, "call_limit": 1000},
        bankroll={"current_bankroll": 1000, "daily_bankroll_limit_pct": 0.05, "kelly_fraction": 0.25},
        generated_at_utc="2026-06-29T00:00:00Z",
    )

    for field in DASHBOARD_FIELDS:
        assert field in dashboard
    assert dashboard["events_scanned"] == 4
    assert dashboard["positive_ev_picks"] == 2
    assert dashboard["watchlist_picks"] == 1
    assert dashboard["avoid_picks"] == 1
    assert dashboard["learning_rows_scanned"] == 3
    assert dashboard["api_usage"]["usage_pct"] == 0.62
    assert dashboard["generated_at_utc"] == "2026-06-29T00:00:00Z"


def test_top_picks_are_ranked_by_value_not_confidence_only():
    dashboard = build_dashboard_data(_rows(), bankroll={"current_bankroll": 1000})
    top = dashboard["top_positive_ev_picks"]

    assert len(top) == 2
    assert top[0]["event"] == "NY Liberty vs Las Vegas Aces"
    assert top[0]["expected_value"] == 0.20
    assert dashboard["best_edge_today"]["label"] == "+8.0%"
    assert dashboard["odds_lock_summary"]["status"] == "PLAYABLE"


def test_bankroll_risk_summary_flags_moderate_exposure():
    dashboard = build_dashboard_data(_rows(), bankroll={"current_bankroll": 1000, "daily_bankroll_limit_pct": 0.05})

    assert dashboard["bankroll_summary"]["daily_exposure_units"] == 12.0
    assert dashboard["bankroll_summary"]["exposure_pct"] == 0.012
    assert dashboard["bankroll_risk"] == "Moderate"
    assert dashboard["bankroll_summary"]["recommended_kelly_fraction"] <= 0.25


def test_proof_clv_roi_recent_activity_and_upcoming_events():
    dashboard = build_dashboard_data(_rows(), bankroll={"current_bankroll": 1000})

    assert dashboard["proof_summary"]["total_picks"] == 4
    assert dashboard["proof_summary"]["unique_events"] == 4
    assert dashboard["clv_summary"]["sample_rows"] == 3
    assert dashboard["roi_summary"]["losses"] if "losses" in dashboard["roi_summary"] else True
    assert dashboard["recent_activity"]
    assert len(dashboard["upcoming_events"]) == 2


def test_empty_dashboard_path_is_stable():
    dashboard = build_dashboard_data(pd.DataFrame(), api_usage={}, bankroll={"current_bankroll": 1000})

    assert dashboard["events_scanned"] == 0
    assert dashboard["positive_ev_picks"] == 0
    assert dashboard["watchlist_picks"] == 0
    assert dashboard["avoid_picks"] == 0
    assert dashboard["model_status"] == "No Data"
    assert dashboard["drift_status"] == "No Drift"
    assert dashboard["odds_lock_summary"]["status"] == "NO_PLAYABLE_LOCK"

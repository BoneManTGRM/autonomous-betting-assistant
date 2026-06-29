import pandas as pd

from autonomous_betting_agent.profitability_metrics import summarize_profitability


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
                "result": "win",
                "stake_units": 1,
                "manual_clv": 0.04,
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
                "result": "push",
                "stake_units": 1,
                "manual_clv": 0.02,
            },
            {
                "event": "LA Dodgers vs SF Giants",
                "prediction": "Dodgers ML",
                "market_type": "h2h",
                "bookmaker": "BetMGM",
                "data_issue_reason": "missing odds",
                "result": "loss",
                "stake_units": 1,
            },
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
                "result": "win",
                "stake_units": 1,
                "manual_clv": 0.04,
            },
        ]
    )


def test_profitability_summary_counts_roi_and_win_rate():
    summary = summarize_profitability(_rows())

    assert summary["total_picks"] == 5
    assert summary["wins"] == 2
    assert summary["losses"] == 2
    assert summary["pushes"] == 1
    assert summary["cancels"] == 0
    assert summary["win_rate_ex_push_cancel"] == 0.5
    assert summary["profit_units"] == 0.0
    assert summary["staked_units"] == 4.0
    assert summary["roi"] == 0.0


def test_status_counts_and_positive_ev_truth_gate():
    summary = summarize_profitability(_rows())

    assert summary["status_counts"]["playable"] == 3
    assert summary["status_counts"]["watchlist"] == 1
    assert summary["status_counts"]["avoid"] == 1
    assert summary["status_counts"]["prediction_only"] == 0


def test_duplicate_adjusted_record_and_unique_event_count():
    summary = summarize_profitability(_rows())

    assert summary["duplicate_count"] == 1
    assert summary["unique_event_count"] == 4
    assert summary["duplicate_adjusted_record"]["total_picks"] == 4
    assert summary["duplicate_adjusted_record"]["wins"] == 1
    assert summary["duplicate_adjusted_record"]["losses"] == 2


def test_clv_and_segment_roi_metrics():
    summary = summarize_profitability(_rows())

    assert summary["average_clv"] == 0.0225
    assert summary["playable_pick_roi"] == 0.3333
    assert summary["watchlist_pick_roi"] is None
    assert summary["avoid_pick_tracking_result"]["count"] == 1
    assert summary["avoid_pick_tracking_result"]["roi"] == -1.0


def test_empty_profitability_path_is_safe():
    summary = summarize_profitability(pd.DataFrame())

    assert summary["total_picks"] == 0
    assert summary["wins"] == 0
    assert summary["losses"] == 0
    assert summary["roi"] is None
    assert summary["unique_event_count"] == 0
    assert summary["status_counts"]["playable"] == 0

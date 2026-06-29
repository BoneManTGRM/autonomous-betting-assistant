import pandas as pd

from autonomous_betting_agent.profitability_metrics import (
    bankroll_summary,
    profitability_summary,
    top_positive_ev_picks,
)


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
            },
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
            },
        ]
    )


def test_profitability_summary_core_metrics_and_duplicate_adjusted_record():
    summary = profitability_summary(_rows())

    assert summary["total_picks"] == 5
    assert summary["wins"] == 2
    assert summary["losses"] == 1
    assert summary["pushes"] == 1
    assert summary["cancels"] == 1
    assert summary["win_rate_ex_push_cancel"] == 0.666667
    assert summary["profit_units"] == 0.8
    assert round(summary["roi"], 6) == 0.2
    assert summary["unique_event_count"] == 4
    assert summary["duplicate_count"] == 1
    assert summary["duplicate_adjusted_record"]["wins"] == 1
    assert summary["duplicate_adjusted_record"]["losses"] == 1
    assert summary["lane_counts"]["playable"] == 3
    assert summary["lane_counts"]["watchlist"] == 1
    assert summary["lane_counts"]["avoid"] == 1


def test_average_edge_no_vig_clv_and_lane_roi_summaries():
    summary = profitability_summary(_rows())

    assert summary["average_edge"] is not None
    assert summary["average_no_vig_edge"] is not None
    assert summary["average_clv"] == 0.016667
    assert summary["playable_pick_roi"]["total_picks"] == 3
    assert summary["watchlist_pick_roi"]["pushes"] == 1
    assert summary["avoid_pick_tracking_result"]["cancels"] == 1
    assert summary["clv_summary"]["positive_clv_count"] == 2
    assert summary["clv_summary"]["negative_clv_count"] == 1


def test_top_positive_ev_picks_rank_by_ev_edge_no_vig_and_not_confidence_only():
    top = top_positive_ev_picks(_rows(), limit=5)

    assert len(top) == 3
    assert top[0]["event"] == "Aces vs Liberty"
    assert all(item["status"] == "PLAYABLE" for item in top)
    assert all(item["expected_value"] and item["expected_value"] > 0 for item in top)
    assert not any(item["event"] == "Carlos Alcaraz vs D Medvedev" for item in top)
    assert not any(item["event"] == "Dodgers vs Giants" for item in top)


def test_bankroll_summary_flags_low_moderate_high_blocked_risk():
    rows = _rows()

    low = bankroll_summary(rows, bankroll=1000, unit_size=5, max_daily_fraction=0.05)
    moderate = bankroll_summary(rows, bankroll=100, unit_size=2, max_daily_fraction=0.05)
    blocked = bankroll_summary(rows, bankroll=20, unit_size=5, max_daily_fraction=0.05)

    assert low["risk_level"] == "Low"
    assert moderate["risk_level"] == "High"
    assert blocked["risk_level"] == "Blocked"
    assert low["recommended_bets"] == 3
    assert low["kelly_fraction"] >= 0


def test_empty_missing_data_safety_path():
    summary = profitability_summary(pd.DataFrame())
    bank = bankroll_summary(pd.DataFrame())
    top = top_positive_ev_picks(pd.DataFrame())

    assert summary["total_picks"] == 0
    assert summary["unique_event_count"] == 0
    assert summary["profit_units"] == 0
    assert bank["risk_level"] == "Low"
    assert bank["recommended_bets"] == 0
    assert top == []

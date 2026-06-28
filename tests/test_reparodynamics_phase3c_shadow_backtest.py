from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.reparodynamics_shadow_backtest import (
    baseline_metrics,
    build_phase3c_report,
    calculate_clv,
    classify_findings,
    classify_shadow_decision,
    compare_baseline_to_shadow,
    simulate_shadow_repairs,
)
from autonomous_betting_agent.ui_i18n import localize_dataframe


def sample_rows(count: int = 60, sport: str = "Tennis"):
    return [
        {
            "sport": sport,
            "league": "FIFA World Cup" if sport == "Soccer" else sport,
            "market_type": "moneyline",
            "result": "win" if index % 2 == 0 else "loss",
            "decimal_price": 2.0,
            "closing_decimal_price": 1.9,
            "stake_units": 1.0,
            "model_probability": 0.60,
            "edge": 0.02,
        }
        for index in range(count)
    ]


def test_missing_closing_price_is_data_blocker_not_candidate():
    findings = classify_findings([{"result": "win", "decimal_price": 1.8}])
    assert any(item["finding_type"] == "data_blocker" for item in findings)
    assert not any(item["finding_type"] == "repair_candidate" for item in findings)


def test_zero_rows_are_watchlist_not_candidate():
    findings = classify_findings([])
    assert any(item["finding_type"] == "watchlist" for item in findings)
    assert not any(item["finding_type"] == "repair_candidate" for item in findings)


def test_baseline_metrics_record_and_roi():
    metrics = baseline_metrics([
        {"result": "win", "decimal_price": 2.0, "stake_units": 1},
        {"result": "loss", "decimal_price": 1.8, "stake_units": 1},
        {"result": "push", "decimal_price": 1.9, "stake_units": 1},
    ])
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["pushes"] == 1
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_units"] == 0.0
    assert metrics["ROI"] == 0.0


def test_clv_calculation_and_missing_close():
    assert calculate_clv({"decimal_price": 2.0, "closing_decimal_price": 1.8}) == 0.111111
    assert calculate_clv({"decimal_price": 2.0}) is None
    assert calculate_clv({"clv_percent": "+5"}) == 0.05


def test_shadow_options_and_market_specific_blockers():
    options = simulate_shadow_repairs(sample_rows(60, sport="Soccer"))
    names = {item["candidate_type"] for item in options}
    assert "no_play" in names
    assert "reduce_stake_50_percent" in names
    assert next(item for item in options if item["candidate_type"] == "draw_no_bet_if_available")["decision"] == "data_blocked"
    assert next(item for item in options if item["candidate_type"] == "double_chance_if_available")["decision"] == "data_blocked"


def test_non_soccer_rows_do_not_create_fake_loss_filter_repairs():
    assert simulate_shadow_repairs(sample_rows(60, sport="Tennis")) == []


def test_comparison_has_deltas_and_rejects_worse_result():
    comparison = compare_baseline_to_shadow(
        {"completed_rows_used": 60, "ROI": 0.1, "profit_units": 10, "losses": 10, "CLV_sample_size": 0},
        {"completed_rows_used": 60, "ROI": 0.0, "profit_units": 0, "losses": 12, "CLV_sample_size": 0},
    )
    assert "ROI_delta" in comparison
    assert comparison["decision"] == "rejected_repair"


def test_strong_shadow_improvement_becomes_manual_review_not_live_repair():
    decision = classify_shadow_decision(
        {
            "baseline_sample_size": 60,
            "ROI_delta": 0.05,
            "profit_units_delta": 2.0,
            "losses_delta": -3,
            "CLV_delta": None,
            "overfit_risk": "low",
        }
    )
    assert decision["decision"] == "future_manual_review"


def test_phase3c_report_safety_invariants():
    report = build_phase3c_report(sample_rows())
    assert report["live_mutation"] == "FORBIDDEN"
    assert report["model_training"] == "FORBIDDEN"
    assert report["stored_data_mutation"] == "FORBIDDEN"
    assert report["repairs_applied_live"] == 0
    assert report["summary_counts"]["live_repairs_applied_count"] == 0


def test_spanish_phase3c_display_localizes_columns_and_values():
    out = localize_dataframe(pd.DataFrame([{"finding_type": "data_blocker", "candidate_type": "no_play", "live_mutation": "FORBIDDEN"}]), "es")
    assert "Tipo de hallazgo" in out.columns
    assert out.iloc[0]["Tipo de hallazgo"] == "bloqueador de datos"
    assert out.iloc[0]["Tipo de candidato"] == "no jugar"
    assert out.iloc[0]["Mutacion en vivo"] == "prohibido"

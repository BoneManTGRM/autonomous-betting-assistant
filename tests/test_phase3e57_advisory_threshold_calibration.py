from __future__ import annotations

from copy import deepcopy

import pandas as pd

from autonomous_betting_agent.advisory_odds_value_display import advisory_csv_frame, proof_safety_comparison, fresh_slate_readiness_check
from autonomous_betting_agent.advisory_threshold_calibration import (
    PLAYABLE_PLUS_EV,
    PREDICTION_ONLY_NOT_PLUS_EV,
    WATCHLIST_VALUE,
    advisory_threshold_presets,
    apply_advisory_thresholds,
    calibrated_status_table,
    default_advisory_threshold_config,
    normalize_threshold_config,
    threshold_calibration_summary,
    threshold_impact_summary,
    threshold_report_text,
)


def _row(**overrides):
    base = {
        "event": "Team A vs Team B",
        "prediction": "Team A",
        "selection": "Team A",
        "sport": "basketball",
        "market_type": "h2h",
        "bookmaker": "Caliente",
        "event_start_utc": "2099-01-01T00:00:00Z",
        "odds_timestamp": "2099-01-01T00:00:00Z",
        "decimal_odds": 2.10,
        "model_probability": 0.58,
        "advisory_playable_status": "WATCHLIST_VALUE",
        "advisory_raw_EV": 0.08,
        "advisory_best_price_EV": 0.09,
        "advisory_no_vig_edge": 0.04,
        "advisory_market_hold": 0.04,
        "advisory_line_shopping_gain": 0.02,
        "advisory_is_real_sportsbook": True,
        "advisory_is_consensus_source": False,
        "advisory_sportsbook_source_type": "REAL_SPORTSBOOK",
        "advisory_market_completeness_status": "COMPLETE_MARKET",
        "advisory_no_vig_available": True,
        "advisory_stale_line_status": "FRESH",
        "advisory_stale_line_reason": "odds_timestamp_within_threshold",
        "advisory_duplicate_event_status": "UNIQUE_EVENT",
        "advisory_conflict_status": "NO_CONFLICT",
        "proof_hash": "proofhash",
        "proof_id": "proofid",
        "locked_at_utc": "2098-01-01T00:00:00Z",
        "lock_ready": False,
        "official_lock_ready": False,
        "publish_ready": False,
        "result_status": "pending",
    }
    base.update(overrides)
    return base


def _count(rows, status):
    return sum(1 for row in rows if row.get("advisory_calibrated_playable_status") == status)


def test_default_balanced_config_and_presets_exist():
    default = default_advisory_threshold_config()
    presets = advisory_threshold_presets()
    assert default["advisory_threshold_preset"] == "Balanced"
    assert {"Conservative", "Balanced", "Aggressive"}.issubset(set(presets))


def test_custom_config_normalizes_and_clamps_invalid_values():
    config = normalize_threshold_config({
        "advisory_threshold_preset": "Custom",
        "advisory_threshold_min_raw_ev": 99,
        "advisory_threshold_max_market_hold": -5,
        "advisory_threshold_max_risk_flags": 100,
    })
    assert config["advisory_threshold_preset"] == "Custom"
    assert config["advisory_threshold_min_raw_ev"] <= 1.0
    assert config["advisory_threshold_max_market_hold"] >= 0.0
    assert config["advisory_threshold_max_risk_flags"] <= 25


def test_hard_blocked_rows_cannot_become_playable_under_aggressive():
    aggressive = advisory_threshold_presets()["Aggressive"]
    rows = [
        _row(advisory_playable_status="BLOCKED_STALE_LINE", advisory_stale_line_status="STALE", advisory_stale_line_reason="odds_timestamp_older_than_threshold"),
        _row(advisory_sportsbook_source_type="CONSENSUS_ONLY", advisory_is_real_sportsbook=False, advisory_is_consensus_source=True),
        _row(advisory_sportsbook_source_type="UNKNOWN_SOURCE", advisory_is_real_sportsbook=False),
        _row(advisory_market_completeness_status="INCOMPLETE_MARKET", advisory_no_vig_available=False, advisory_no_vig_blocker_reason="market_incomplete_no_vig_unavailable"),
        _row(advisory_no_vig_available=False, advisory_no_vig_blocker_reason="market_incomplete_no_vig_unavailable"),
    ]
    out = apply_advisory_thresholds(rows, aggressive)
    assert all(row["advisory_calibrated_playable_status"] != PLAYABLE_PLUS_EV for row in out)


def test_balanced_can_make_clean_row_playable():
    out = apply_advisory_thresholds([_row()], default_advisory_threshold_config())
    assert out[0]["advisory_calibrated_playable_status"] == PLAYABLE_PLUS_EV
    assert out[0]["advisory_playable_status"] == "WATCHLIST_VALUE"
    assert out[0]["advisory_original_playable_status_before_thresholds"] == "WATCHLIST_VALUE"


def test_soft_threshold_failure_becomes_watchlist_or_prediction_only_not_hard_blocked():
    out = apply_advisory_thresholds([_row(advisory_raw_EV=0.005, advisory_no_vig_edge=0.002, advisory_best_price_EV=0.01)], default_advisory_threshold_config())
    assert out[0]["advisory_calibrated_playable_status"] in {WATCHLIST_VALUE, PREDICTION_ONLY_NOT_PLUS_EV}
    assert not out[0]["advisory_calibrated_playable_status"].startswith("BLOCKED")
    assert out[0]["advisory_threshold_failed_reasons"]


def test_conservative_reduces_and_aggressive_increases_or_preserves_playable_count():
    rows = [
        _row(advisory_raw_EV=0.08, advisory_best_price_EV=0.09, advisory_no_vig_edge=0.04, advisory_market_hold=0.04, model_probability=0.58),
        _row(advisory_raw_EV=0.035, advisory_best_price_EV=0.045, advisory_no_vig_edge=0.021, advisory_market_hold=0.07, model_probability=0.53),
        _row(advisory_raw_EV=0.015, advisory_best_price_EV=0.025, advisory_no_vig_edge=0.006, advisory_market_hold=0.09, model_probability=0.51),
    ]
    conservative = apply_advisory_thresholds(rows, advisory_threshold_presets()["Conservative"])
    balanced = apply_advisory_thresholds(rows, advisory_threshold_presets()["Balanced"])
    aggressive = apply_advisory_thresholds(rows, advisory_threshold_presets()["Aggressive"])
    assert _count(conservative, PLAYABLE_PLUS_EV) <= _count(balanced, PLAYABLE_PLUS_EV)
    assert _count(aggressive, PLAYABLE_PLUS_EV) >= _count(balanced, PLAYABLE_PLUS_EV)


def test_threshold_impact_and_calibration_summary():
    rows = [_row(), _row(advisory_raw_EV=0.0, advisory_no_vig_edge=0.0, advisory_best_price_EV=0.0)]
    calibrated = apply_advisory_thresholds(rows, default_advisory_threshold_config())
    impact = threshold_impact_summary(rows, calibrated)
    assert impact["total_rows"] == 2
    assert "calibrated_PLAYABLE_PLUS_EV" in impact
    summary = threshold_calibration_summary(rows, default_advisory_threshold_config())
    assert {"threshold_preset", "threshold_name", "threshold_value", "rows_passed", "rows_failed", "most_common_failed_reason"}.issubset(summary.columns)


def test_csv_and_threshold_report_include_threshold_fields():
    calibrated = apply_advisory_thresholds([_row()], default_advisory_threshold_config())
    csv = advisory_csv_frame(calibrated)
    assert "advisory_calibrated_playable_status" in csv.columns
    assert "advisory_threshold_failed_reasons" in csv.columns
    report = threshold_report_text(calibrated, default_advisory_threshold_config())
    assert "Advisory Threshold Calibration" in report
    assert "Preset: Balanced" in report
    assert "Calibration is advisory-only" in report


def test_readiness_does_not_fail_when_conservative_produces_zero_playable():
    rows = [_row(advisory_raw_EV=0.02, advisory_best_price_EV=0.02, advisory_no_vig_edge=0.01, advisory_market_hold=0.07, model_probability=0.53)]
    readiness = fresh_slate_readiness_check(rows, now="2098-12-31T23:00:00Z")
    conservative = apply_advisory_thresholds(rows, advisory_threshold_presets()["Conservative"])
    assert _count(conservative, PLAYABLE_PLUS_EV) == 0
    assert readiness["readiness_status"] != "MISSING_CRITICAL_FIELDS"


def test_calibration_does_not_mutate_original_proof_or_official_fields():
    rows = [_row(official_ev_pick=True, stake_units=3)]
    before = deepcopy(rows)
    out = apply_advisory_thresholds(rows, default_advisory_threshold_config())
    assert rows == before
    assert proof_safety_comparison(rows, out)["passed"] is True


def test_missing_odds_timestamp_produces_reason_and_no_crash():
    row = _row()
    row.pop("odds_timestamp", None)
    out = apply_advisory_thresholds([row], default_advisory_threshold_config())
    assert "odds_age_unavailable" in out[0]["advisory_threshold_failed_reasons"]


def test_risk_flag_count_excludes_proof_lock_result_and_grading_fields():
    row = _row(proof_warning=True, lock_flag=True, result_risk=True, grade_warning=True, advisory_custom_warning=True)
    out = apply_advisory_thresholds([row], default_advisory_threshold_config())
    flags = out[0]["advisory_threshold_risk_flags"]
    assert "advisory_custom_warning" in flags
    assert "proof_warning" not in flags
    assert "lock_flag" not in flags
    assert "result_risk" not in flags
    assert "grade_warning" not in flags


def test_calibrated_status_table_filters_status():
    rows = apply_advisory_thresholds([_row(), _row(advisory_raw_EV=-0.5, advisory_no_vig_edge=-0.5)], default_advisory_threshold_config())
    playable = calibrated_status_table(rows, PLAYABLE_PLUS_EV)
    assert not playable.empty
    assert set(playable["advisory_calibrated_playable_status"]) == {PLAYABLE_PLUS_EV}

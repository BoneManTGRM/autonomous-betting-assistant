from __future__ import annotations

from copy import deepcopy

from autonomous_betting_agent.advisory_odds_value_display import advisory_csv_frame, fresh_slate_readiness_check
from autonomous_betting_agent.advisory_validation_dashboard import (
    VALIDATION_CANCEL,
    VALIDATION_LOSS,
    VALIDATION_PENDING,
    VALIDATION_PUSH,
    VALIDATION_UNKNOWN,
    VALIDATION_WIN,
    advisory_validation_group_summary,
    advisory_validation_overall_summary,
    advisory_validation_report_section,
    advisory_validation_rows,
    normalize_validation_result,
)


def _row(**updates):
    row = {
        "event": "Team A vs Team B",
        "prediction": "Team A",
        "market_type": "h2h",
        "sportsbook": "Caliente",
        "bookmaker": "Caliente",
        "decimal_odds": 2.0,
        "stake_units": 1.0,
        "model_probability": 0.58,
        "advisory_raw_ev": 0.12,
        "advisory_clv_decimal_delta": 0.05,
        "advisory_clv_status": "CLV_POSITIVE",
        "advisory_playable_status": "PLAYABLE_PLUS_EV",
        "advisory_calibrated_playable_status": "PLAYABLE_PLUS_EV",
        "advisory_explanation_status": "EXPLAINED_PLAYABLE_PLUS_EV",
        "advisory_candidate_review_status": "MANUAL_CANDIDATE_ONLY",
        "advisory_sportsbook_source_type": "REAL_SPORTSBOOK",
        "advisory_market_completeness_status": "COMPLETE_MARKET",
        "advisory_no_vig_available": True,
        "event_start_utc": "2099-01-01T00:00:00Z",
        "odds_timestamp": "2099-01-01T00:00:00Z",
        "result_status": "win",
    }
    row.update(updates)
    return row


def test_normalize_validation_result_aliases():
    assert normalize_validation_result({"result_status": "win"}) == VALIDATION_WIN
    assert normalize_validation_result({"result_status": "loss"}) == VALIDATION_LOSS
    assert normalize_validation_result({"result_status": "push"}) == VALIDATION_PUSH
    assert normalize_validation_result({"result_status": "cancelled"}) == VALIDATION_CANCEL
    assert normalize_validation_result({"result_status": "pending"}) == VALIDATION_PENDING
    assert normalize_validation_result({}) == VALIDATION_UNKNOWN


def test_row_count_and_unique_event_count_are_separate():
    rows = advisory_validation_rows([
        _row(event="Same Game", result_status="win"),
        _row(event="Same Game", prediction="Team B", result_status="loss"),
        _row(event="Other Game", result_status="push"),
    ])
    summary = advisory_validation_overall_summary(rows).iloc[0].to_dict()
    assert summary["row_count"] == 3
    assert summary["unique_event_count"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["pushes"] == 1
    assert summary["usable_graded_count"] == 2
    assert summary["win_rate_excluding_push_cancel"] == 0.5


def test_cancels_and_pushes_excluded_from_win_rate():
    rows = advisory_validation_rows([
        _row(result_status="win"),
        _row(result_status="push"),
        _row(result_status="cancelled"),
    ])
    summary = advisory_validation_overall_summary(rows).iloc[0].to_dict()
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["pushes"] == 1
    assert summary["cancels"] == 1
    assert summary["usable_graded_count"] == 1
    assert summary["win_rate_excluding_push_cancel"] == 1.0


def test_roi_calculated_only_when_stake_and_odds_exist():
    rows = advisory_validation_rows([
        _row(result_status="win", decimal_odds=2.5, stake_units=2.0),
        _row(result_status="loss", decimal_odds=2.0, stake_units=1.0),
        _row(result_status="win", decimal_odds=None, stake_units=None),
    ])
    summary = advisory_validation_overall_summary(rows).iloc[0].to_dict()
    assert summary["roi_rows"] == 2
    assert summary["roi_percent"] == 0.666667


def test_group_summaries_by_key_categories():
    rows = advisory_validation_rows([
        _row(advisory_calibrated_playable_status="PLAYABLE_PLUS_EV", result_status="win"),
        _row(advisory_calibrated_playable_status="WATCHLIST_VALUE", advisory_clv_status="CLV_NEGATIVE", result_status="loss"),
    ])
    by_status = advisory_validation_group_summary(rows, "advisory_calibrated_playable_status")
    by_clv = advisory_validation_group_summary(rows, "advisory_clv_status")
    assert "advisory_calibrated_playable_status" in by_status.columns
    assert "advisory_clv_status" in by_clv.columns
    assert int(by_status["row_count"].sum()) == 2
    assert int(by_clv["row_count"].sum()) == 2


def test_missing_results_are_safe_and_input_not_mutated():
    rows = [_row(result_status="pending"), _row(result_status=None)]
    before = deepcopy(rows)
    out = advisory_validation_rows(rows)
    assert rows == before
    statuses = {row["advisory_validation_result_status"] for row in out}
    assert VALIDATION_PENDING in statuses
    assert VALIDATION_UNKNOWN in statuses


def test_report_csv_and_readiness_accept_validation_fields():
    rows = advisory_validation_rows([_row(result_status="win")])
    report = advisory_validation_report_section(rows)
    csv_frame = advisory_csv_frame(rows)
    readiness = fresh_slate_readiness_check(rows, now="2098-12-31T00:00:00Z")
    assert "Advisory Performance Validation Dashboard" in report
    assert "advisory_validation_result_status" in csv_frame.columns
    assert "advisory_validation_event_key" in csv_frame.columns
    assert readiness["readiness_status"] in {
        "READY_FOR_ADVISORY_VALUE",
        "PARTIALLY_READY",
        "NEEDS_COMPLETE_MARKETS",
        "NEEDS_REAL_SPORTSBOOK_PRICES",
    }

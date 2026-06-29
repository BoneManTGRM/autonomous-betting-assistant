from __future__ import annotations

from copy import deepcopy

from autonomous_betting_agent.advisory_explanation_engine import (
    EXPLAINED_BLOCKED,
    EXPLAINED_MARKET_INCOMPLETE,
    EXPLAINED_NO_VIG_UNAVAILABLE,
    EXPLAINED_PLAYABLE_PLUS_EV,
    EXPLAINED_PREDICTION_ONLY,
    EXPLAINED_SOURCE_BLOCKED,
    EXPLAINED_STALE_OR_HISTORICAL,
    EXPLAINED_THRESHOLD_DOWNGRADED,
    EXPLAINED_UNKNOWN,
    EXPLAINED_WATCHLIST_VALUE,
    advisory_explanation_reason_counts,
    advisory_explanation_report_section,
    advisory_explanation_summary,
    explain_advisory_row,
    explain_advisory_rows,
)
from autonomous_betting_agent.advisory_odds_value_display import advisory_csv_frame, fresh_slate_readiness_check, proof_safety_comparison


def _base(**overrides):
    row = {
        "event": "Team A vs Team B",
        "prediction": "Team A",
        "market_type": "h2h",
        "bookmaker": "Caliente",
        "model_probability": 0.58,
        "decimal_odds": 2.1,
        "advisory_playable_status": "WATCHLIST_VALUE",
        "advisory_sportsbook_source_type": "REAL_SPORTSBOOK",
        "advisory_is_real_sportsbook": True,
        "advisory_is_consensus_source": False,
        "advisory_market_completeness_status": "COMPLETE_MARKET",
        "advisory_no_vig_available": True,
        "advisory_stale_line_status": "FRESH",
        "advisory_threshold_passed": True,
        "advisory_shadow_readiness_status": "READY_FOR_OBSERVATION_ONLY",
        "advisory_shadow_readiness_score": 70,
        "advisory_shadow_observation_only": True,
        "advisory_shadow_live_mutation_allowed": False,
        "proof_hash": "abc",
        "official_lock_ready": False,
        "result_status": "pending",
    }
    row.update(overrides)
    return row


def test_core_status_explanations():
    assert explain_advisory_row(_base(advisory_playable_status="PLAYABLE_PLUS_EV"))["advisory_explanation_status"] == EXPLAINED_PLAYABLE_PLUS_EV
    assert explain_advisory_row(_base(advisory_playable_status="WATCHLIST_VALUE"))["advisory_explanation_status"] == EXPLAINED_WATCHLIST_VALUE
    assert explain_advisory_row(_base(advisory_playable_status="PREDICTION_ONLY_NOT_PLUS_EV"))["advisory_explanation_status"] == EXPLAINED_PREDICTION_ONLY
    assert explain_advisory_row(_base(advisory_playable_status="BLOCKED_MISSING_ODDS", advisory_playable_reason="missing_decimal_odds"))["advisory_explanation_status"] == EXPLAINED_BLOCKED


def test_blocked_specific_explanations():
    stale = _base(advisory_stale_line_status="STALE", advisory_playable_reason="event_start_time_is_not_future")
    assert explain_advisory_row(stale)["advisory_explanation_status"] == EXPLAINED_STALE_OR_HISTORICAL
    consensus = _base(advisory_sportsbook_source_type="CONSENSUS_ONLY", advisory_is_consensus_source=True, advisory_is_real_sportsbook=False)
    assert explain_advisory_row(consensus)["advisory_explanation_status"] == EXPLAINED_SOURCE_BLOCKED
    unknown = _base(advisory_sportsbook_source_type="UNKNOWN_SOURCE", advisory_is_real_sportsbook=False)
    assert explain_advisory_row(unknown)["advisory_explanation_status"] == EXPLAINED_SOURCE_BLOCKED
    incomplete = _base(advisory_market_completeness_status="INCOMPLETE_MARKET", advisory_no_vig_available=True)
    assert explain_advisory_row(incomplete)["advisory_explanation_status"] == EXPLAINED_MARKET_INCOMPLETE
    no_vig = _base(advisory_market_completeness_status="COMPLETE_MARKET", advisory_no_vig_available=False)
    assert explain_advisory_row(no_vig)["advisory_explanation_status"] == EXPLAINED_NO_VIG_UNAVAILABLE


def test_threshold_downgraded_and_shadow_notes():
    row = _base(
        advisory_playable_status="PLAYABLE_PLUS_EV",
        advisory_original_playable_status_before_thresholds="PLAYABLE_PLUS_EV",
        advisory_calibrated_playable_status="WATCHLIST_VALUE",
        advisory_threshold_failed_reasons="no_vig_edge_below_threshold",
        advisory_shadow_readiness_status="NEEDS_MORE_COMPLETED_EVENTS",
    )
    out = explain_advisory_row(row)
    assert out["advisory_explanation_status"] == EXPLAINED_THRESHOLD_DOWNGRADED
    assert "threshold_downgraded" in out["advisory_explanation_reason_codes"]
    assert out["advisory_explanation_shadow_notes"]


def test_output_fields_present_and_missing_fields_unknown():
    out = explain_advisory_row(_base())
    for field in [
        "advisory_explanation_summary",
        "advisory_explanation_reason_codes",
        "advisory_explanation_blockers",
        "advisory_explanation_warnings",
        "advisory_explanation_next_action",
    ]:
        assert field in out
    unknown = explain_advisory_row({"event": "missing advisory fields"})
    assert unknown["advisory_explanation_status"] == EXPLAINED_UNKNOWN
    assert "Missing advisory fields" in unknown["advisory_explanation_warnings"]


def test_summary_reason_counts_csv_and_report_include_explanations():
    rows = explain_advisory_rows([
        _base(advisory_playable_status="PLAYABLE_PLUS_EV"),
        _base(advisory_playable_status="WATCHLIST_VALUE"),
        _base(advisory_sportsbook_source_type="CONSENSUS_ONLY", advisory_is_consensus_source=True, advisory_is_real_sportsbook=False),
    ])
    summary = advisory_explanation_summary(rows)
    reasons = advisory_explanation_reason_counts(rows)
    csv = advisory_csv_frame(rows)
    report = advisory_explanation_report_section(rows)
    assert "explanation_status" in summary.columns
    assert "reason_code" in reasons.columns
    assert "advisory_explanation_status" in csv.columns
    assert "Advisory Explanation Engine" in report
    assert "Top reason codes" in report


def test_fresh_slate_readiness_does_not_fail_due_to_explanations():
    rows = explain_advisory_rows([_base(event_start_utc="2099-01-01T00:00:00Z", odds_timestamp="2099-01-01T00:00:00Z")])
    readiness = fresh_slate_readiness_check(rows, now="2098-12-31T00:00:00Z")
    assert readiness["readiness_status"] in {"READY_FOR_ADVISORY_VALUE", "PARTIALLY_READY", "NEEDS_COMPLETE_MARKETS", "NEEDS_REAL_SPORTSBOOK_PRICES"}


def test_explanations_do_not_mutate_input_or_proof_official_result_fields():
    rows = [_base()]
    before = deepcopy(rows)
    out = explain_advisory_rows(rows)
    assert rows == before
    assert proof_safety_comparison(rows, out)["passed"] is True


def test_precedence_multiple_blockers():
    stale_consensus = _base(advisory_stale_line_status="STALE", advisory_sportsbook_source_type="CONSENSUS_ONLY", advisory_is_consensus_source=True)
    assert explain_advisory_row(stale_consensus)["advisory_explanation_status"] == EXPLAINED_STALE_OR_HISTORICAL
    source_incomplete = _base(advisory_sportsbook_source_type="CONSENSUS_ONLY", advisory_is_consensus_source=True, advisory_market_completeness_status="INCOMPLETE_MARKET")
    assert explain_advisory_row(source_incomplete)["advisory_explanation_status"] == EXPLAINED_SOURCE_BLOCKED
    market_no_vig = _base(advisory_market_completeness_status="INCOMPLETE_MARKET", advisory_no_vig_available=False)
    assert explain_advisory_row(market_no_vig)["advisory_explanation_status"] == EXPLAINED_MARKET_INCOMPLETE
    threshold_blocked = _base(advisory_playable_status="BLOCKED_MISSING_ODDS", advisory_playable_reason="missing_decimal_odds", advisory_original_playable_status_before_thresholds="PLAYABLE_PLUS_EV", advisory_calibrated_playable_status="WATCHLIST_VALUE")
    assert explain_advisory_row(threshold_blocked)["advisory_explanation_status"] == EXPLAINED_BLOCKED
    shadow_context = _base(advisory_playable_status="WATCHLIST_VALUE", advisory_shadow_readiness_status="NEEDS_MORE_COMPLETED_EVENTS")
    assert explain_advisory_row(shadow_context)["advisory_explanation_status"] == EXPLAINED_WATCHLIST_VALUE
    assert "shadow_undertrained" in explain_advisory_row(shadow_context)["advisory_explanation_reason_codes"]

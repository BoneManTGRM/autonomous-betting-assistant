from __future__ import annotations

from copy import deepcopy

import pandas as pd

import autonomous_betting_agent.advisory_i18n_phase3e5  # noqa: F401
from autonomous_betting_agent.advisory_odds_value_display import (
    advisory_real_file_diagnostics,
    advisory_report_text,
    proof_safety_comparison,
)
from autonomous_betting_agent.ui_i18n import localize_dataframe

NOW = "2026-06-28T22:34:00Z"


def advisory_row(index: int, *, completeness: str, event_start: str, reason: str = "event_start_time_is_not_future") -> dict[str, object]:
    return {
        "event": f"Historical Game {index}",
        "prediction": f"Team {index}",
        "sport": "basketball",
        "league": "test league",
        "market_type": "h2h",
        "bookmaker": "consensus_average",
        "model_probability": 0.56,
        "decimal_price": 1.91,
        "expected_value_per_unit": 0.0,
        "model_market_edge": 0.0,
        "lock_ready": False,
        "official_lock_ready": False,
        "publish_ready": False,
        "proof_hash": f"hash-{index}",
        "proof_id": f"proof-{index}",
        "locked_at_utc": "2026-06-22T12:00:00Z",
        "result_status": "pending",
        "event_start_utc": event_start,
        "odds_last_update": "2026-06-22T12:00:00Z",
        "advisory_playable_status": "BLOCKED_STALE_LINE",
        "advisory_playable_reason": reason,
        "advisory_market_completeness_status": completeness,
        "advisory_stale_line_status": "EVENT_STARTED",
        "advisory_duplicate_event_status": "UNIQUE_EVENT",
        "advisory_conflict_status": "NO_CONFLICT",
    }


def synthetic_148_row_historical_pattern() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(148):
        completeness = "COMPLETE_MARKET" if index < 55 else "INCOMPLETE_MARKET"
        event_start = "2026-06-28T21:30:00Z" if index == 147 else "2026-06-22T12:00:00Z"
        rows.append(advisory_row(index, completeness=completeness, event_start=event_start))
    return rows


def test_148_row_historical_pattern_explains_zero_playable_rows() -> None:
    rows = synthetic_148_row_historical_pattern()
    diagnostics = advisory_real_file_diagnostics(rows, now=NOW)
    assert diagnostics["total_rows"] == 148
    assert diagnostics["playable_plus_ev_rows"] == 0
    assert diagnostics["watchlist_value_rows"] == 0
    assert diagnostics["prediction_only_rows"] == 0
    assert diagnostics["blocked_rows"] == 148
    assert diagnostics["complete_markets"] == 55
    assert diagnostics["incomplete_markets"] == 93
    assert diagnostics["top_blocked_reason"] == "event_start_time_is_not_future"
    assert diagnostics["top_blocked_row_count"] == 148
    assert diagnostics["file_slate_classification"] == "HISTORICAL_ONLY"
    assert diagnostics["all_rows_blocked_by_non_future_events"] is True
    assert diagnostics["show_no_playable_warning"] is True
    assert "fresh future-event odds file" in diagnostics["recommended_next_action"]
    assert diagnostics["earliest_event_start_time"] is not None
    assert diagnostics["latest_event_start_time"] is not None
    assert diagnostics["current_utc_time"] == "2026-06-28T22:34:00+00:00"


def test_future_file_does_not_show_historical_block_warning() -> None:
    rows = [
        advisory_row(1, completeness="COMPLETE_MARKET", event_start="2026-06-29T22:00:00Z", reason="missing_odds_timestamp"),
    ]
    diagnostics = advisory_real_file_diagnostics(rows, now=NOW)
    assert diagnostics["file_slate_classification"] == "FUTURE_SLATE"
    assert diagnostics["all_rows_blocked_by_non_future_events"] is False
    assert diagnostics["top_blocked_reason"] == "missing_odds_timestamp"


def test_event_start_time_is_not_used_as_odds_freshness_timestamp() -> None:
    row = advisory_row(1, completeness="COMPLETE_MARKET", event_start="2026-06-29T22:00:00Z", reason="missing_odds_timestamp")
    row.pop("odds_last_update")
    diagnostics = advisory_real_file_diagnostics([row], now=NOW)
    assert diagnostics["file_slate_classification"] == "FUTURE_SLATE"
    assert diagnostics["event_start_fields_detected"] == ["event_start_utc"]
    assert diagnostics["odds_freshness_fields_detected"] == []
    assert diagnostics["odds_freshness_timestamp_available_rows"] == 0
    assert "Event-start fields are used only" in diagnostics["timestamp_rule_confirmation"]


def test_diagnostics_do_not_mutate_proof_or_official_fields() -> None:
    rows = synthetic_148_row_historical_pattern()
    before = deepcopy(rows)
    diagnostics = advisory_real_file_diagnostics(rows, now=NOW)
    assert rows == before
    assert diagnostics["proof_safety_check_result"]["passed"] is True
    assert proof_safety_comparison(before, rows)["passed"] is True


def test_report_includes_real_file_diagnostics_summary() -> None:
    rows = synthetic_148_row_historical_pattern()
    report = advisory_report_text(rows)
    assert "Why no playable +EV rows?" in report
    assert "Top blocked reason: event_start_time_is_not_future" in report
    assert "File classification:" in report
    assert "Recommendation:" in report


def test_advisory_labels_still_localize_after_diagnostics_update() -> None:
    frame = pd.DataFrame([{"advisory_playable_status": "BLOCKED_STALE_LINE", "advisory_market_completeness_status": "COMPLETE_MARKET"}])
    localized = localize_dataframe(frame, "es")
    assert any("asesor" in column.lower() for column in localized.columns)
    assert localized.iloc[0, 0] in {"BLOQUEADO LINEA VIEJA", "BLOCKED_STALE_LINE"}

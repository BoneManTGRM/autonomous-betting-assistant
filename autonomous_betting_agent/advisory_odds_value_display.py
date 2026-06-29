from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.advisory_market_completeness import (
    COMPLETE_MARKET,
    MARKET_COMPLETENESS_COLUMNS,
    apply_market_completeness_fields,
    market_completeness_summary,
)
from autonomous_betting_agent.advisory_sportsbook_sources import (
    CONSENSUS_ONLY,
    REAL_SPORTSBOOK,
    UNKNOWN_SOURCE,
    add_sportsbook_source_fields,
    detect_sportsbook_source,
    normalize_sportsbook_source,
    sportsbook_source_counts,
    sportsbook_source_summary,
)
from autonomous_betting_agent.odds_value_engine import (
    BLOCKED_INVALID_PROBABILITY,
    BLOCKED_MISSING_ODDS,
    PLAYABLE_PLUS_EV,
    PREDICTION_ONLY_NOT_PLUS_EV,
    WATCHLIST_VALUE,
    build_advisory_odds_value_rows,
)

ADVISORY_WARNING = (
    "These are advisory value classifications, not official locked bets. "
    "Use them for review until advisory-to-official promotion is added in a later phase."
)
SAFETY_CONFIRMATION = (
    "This report is advisory-only. It does not change proof history, official model probability, "
    "official EV, official edge, lock_ready, publish_ready, locked ledgers, or historical grading. "
    "Live application remains OFF."
)
PLAYABLE_STATUSES = {PLAYABLE_PLUS_EV, WATCHLIST_VALUE, PREDICTION_ONLY_NOT_PLUS_EV}
STALE_WARNING_STATUSES = {"STALE", "UNKNOWN", "EVENT_STARTED", "HISTORICAL_ROW"}
EVENT_START_FIELDS = ["event_start_time", "event_start_utc", "commence_time", "start_utc", "start_time", "game_time", "match_time"]
ODDS_FRESHNESS_FIELDS = ["odds_timestamp", "odds_last_update", "last_update", "pulled_at_utc", "created_at_utc"]
SPORTSBOOK_FIELDS = ["bookmaker", "sportsbook", "book", "book_name", "odds_source", "provider", "source", "sportsbook_name", "casino", "bookie"]
DECIMAL_ODDS_FIELDS = ["decimal_price", "decimal_odds", "odds", "price", "current_decimal_odds"]
MODEL_PROBABILITY_FIELDS = ["model_probability", "model_probability_clean", "final_probability", "probability", "confidence_probability"]
MARKET_TYPE_FIELDS = ["market_type", "market", "bet_type"]
PREDICTION_FIELDS = ["prediction", "selection", "pick", "team", "outcome"]
SHADOW_MODEL_FIELDS = ["lr_model_loaded", "model_loaded", "shadow_model_loaded", "model_source", "shadow_model_status"]
READINESS_STATUSES = {
    "READY_FOR_ADVISORY_VALUE",
    "PARTIALLY_READY",
    "HISTORICAL_ONLY",
    "MISSING_CRITICAL_FIELDS",
    "NEEDS_REAL_SPORTSBOOK_PRICES",
    "NEEDS_COMPLETE_MARKETS",
    "NEEDS_SHADOW_TRAINING",
}
IMMUTABLE_FIELDS = [
    "model_probability", "model_probability_clean", "final_probability", "expected_value_per_unit", "EV", "ev",
    "official_EV", "official_ev", "model_edge", "model_market_edge", "edge", "official_edge",
    "lock_ready", "official_lock_ready", "publish_ready", "proof_hash", "proof_id", "locked_at_utc",
    "result", "grade", "outcome", "official_result", "final_result", "result_status", "pick_result", "settled_status",
]
DISPLAY_KEY_COLUMNS = ["event", "prediction", "sport", "league", "market_type", "sportsbook", "bookmaker"]
SOURCE_COLUMNS = [
    "advisory_original_sportsbook_label",
    "advisory_normalized_sportsbook",
    "advisory_sportsbook_source_type",
    "advisory_is_real_sportsbook",
    "advisory_is_consensus_source",
    "advisory_line_shopping_source_status",
    "advisory_line_shopping_source_reason",
]


def _records(rows: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if isinstance(rows, pd.DataFrame):
        return rows.to_dict("records")
    return [deepcopy(dict(row)) for row in rows if isinstance(row, Mapping)]


def advisory_rows(rows: Sequence[Mapping[str, Any]] | pd.DataFrame, *, config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    source = _records(rows)
    if not source:
        return []
    valued = source if any("advisory_playable_status" in row for row in source) else build_advisory_odds_value_rows(source, config=config)
    sourced = add_sportsbook_source_fields(valued)
    return apply_market_completeness_fields(sourced)


def advisory_frame(rows: Sequence[Mapping[str, Any]] | pd.DataFrame, *, config: Mapping[str, Any] | None = None) -> pd.DataFrame:
    return pd.DataFrame(advisory_rows(rows, config=config))


def _safe_count(frame: pd.DataFrame, column: str, value: Any) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    return int((frame[column].fillna("").astype(str) == str(value)).sum())


def advisory_summary_counts(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> dict[str, int | str]:
    frame = advisory_frame(rows)
    if frame.empty:
        return {
            "total_advisory_rows": 0,
            "PLAYABLE_PLUS_EV": 0,
            "WATCHLIST_VALUE": 0,
            "PREDICTION_ONLY_NOT_PLUS_EV": 0,
            "blocked_rows": 0,
            "stale_rows": 0,
            "unknown_freshness_rows": 0,
            "complete_markets": 0,
            "incomplete_markets": 0,
            "duplicate_conflict_rows": 0,
            "best_price_opportunities": 0,
            "live_application": "OFF",
            "applied_live_count": 0,
        }
    status = frame.get("advisory_playable_status", pd.Series(dtype=str)).fillna("").astype(str)
    stale = frame.get("advisory_stale_line_status", pd.Series(dtype=str)).fillna("").astype(str)
    completeness = frame.get("advisory_market_completeness_status", pd.Series(dtype=str)).fillna("").astype(str)
    duplicate = frame.get("advisory_duplicate_event_status", pd.Series(dtype=str)).fillna("UNIQUE_EVENT").astype(str)
    conflict = frame.get("advisory_conflict_status", pd.Series(dtype=str)).fillna("NO_CONFLICT").astype(str)
    gain = pd.to_numeric(frame.get("advisory_line_shopping_gain", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    return {
        "total_advisory_rows": int(len(frame)),
        "PLAYABLE_PLUS_EV": int((status == PLAYABLE_PLUS_EV).sum()),
        "WATCHLIST_VALUE": int((status == WATCHLIST_VALUE).sum()),
        "PREDICTION_ONLY_NOT_PLUS_EV": int((status == PREDICTION_ONLY_NOT_PLUS_EV).sum()),
        "blocked_rows": int(status.str.startswith("BLOCKED").sum()),
        "stale_rows": int((stale == "STALE").sum()),
        "unknown_freshness_rows": int((stale == "UNKNOWN").sum()),
        "complete_markets": int((completeness == COMPLETE_MARKET).sum()),
        "incomplete_markets": int((completeness != COMPLETE_MARKET).sum()),
        "duplicate_conflict_rows": int(((duplicate != "UNIQUE_EVENT") | (conflict != "NO_CONFLICT")).sum()),
        "best_price_opportunities": int((gain > 0).sum()),
        "live_application": "OFF",
        "applied_live_count": 0,
    }


def _select_columns(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=list(columns))
    selected = [col for col in columns if col in frame.columns]
    return frame[selected].copy() if selected else frame.copy()


def playable_table(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty or "advisory_playable_status" not in frame.columns:
        return pd.DataFrame()
    out = frame[frame["advisory_playable_status"].fillna("").astype(str) == PLAYABLE_PLUS_EV].copy()
    return _select_columns(out, [
        "event", "prediction", "sport", "league", "market_type", "sportsbook", "bookmaker", *SOURCE_COLUMNS, *MARKET_COMPLETENESS_COLUMNS,
        "advisory_playable_status", "advisory_current_decimal_odds", "advisory_best_available_decimal_odds",
        "advisory_best_available_sportsbook", "advisory_raw_EV", "advisory_best_price_EV",
        "advisory_no_vig_edge", "advisory_market_hold", "advisory_line_shopping_gain_pct",
        "advisory_stale_line_status", "advisory_playable_reason",
    ])


def watchlist_table(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty or "advisory_playable_status" not in frame.columns:
        return pd.DataFrame()
    out = frame[frame["advisory_playable_status"].fillna("").astype(str) == WATCHLIST_VALUE].copy()
    return _select_columns(out, [
        "event", "prediction", "sport", "league", "market_type", "sportsbook", "bookmaker", *SOURCE_COLUMNS, *MARKET_COMPLETENESS_COLUMNS,
        "advisory_playable_status", "advisory_current_decimal_odds", "advisory_best_available_decimal_odds",
        "advisory_best_available_sportsbook", "advisory_raw_EV", "advisory_best_price_EV",
        "advisory_no_vig_edge", "advisory_stale_line_status", "advisory_playable_reason",
    ])


def prediction_only_table(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty or "advisory_playable_status" not in frame.columns:
        return pd.DataFrame()
    out = frame[frame["advisory_playable_status"].fillna("").astype(str) == PREDICTION_ONLY_NOT_PLUS_EV].copy()
    return _select_columns(out, [
        "event", "prediction", "model_probability", *SOURCE_COLUMNS, *MARKET_COMPLETENESS_COLUMNS,
        "advisory_playable_status", "advisory_current_decimal_odds", "advisory_raw_EV", "advisory_no_vig_edge",
        "advisory_prediction_only_reason", "advisory_playable_reason",
    ])


def blocked_reason_summary(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty or "advisory_playable_status" not in frame.columns:
        return pd.DataFrame(columns=["advisory_playable_status", "advisory_playable_reason", "row_count"])
    blocked = frame[frame["advisory_playable_status"].fillna("").astype(str).str.startswith("BLOCKED")].copy()
    if blocked.empty:
        return pd.DataFrame(columns=["advisory_playable_status", "advisory_playable_reason", "row_count"])
    grouped = blocked.groupby(["advisory_playable_status", "advisory_playable_reason"], dropna=False).size().reset_index(name="row_count")
    return grouped.sort_values(["row_count", "advisory_playable_status"], ascending=[False, True], ignore_index=True)


def sportsbook_hold_summary(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    work["sportsbook_or_bookmaker"] = work.get("advisory_original_sportsbook_label", pd.Series(index=work.index, dtype=object)).fillna(work.get("sportsbook", pd.Series(index=work.index, dtype=object))).fillna(work.get("bookmaker", pd.Series(index=work.index, dtype=object)))
    if "prediction" in work.columns:
        work["_side"] = work["prediction"].fillna("").astype(str)
    else:
        work["_side"] = ""
    group_cols = [col for col in ["event", "market_type", "sportsbook_or_bookmaker"] if col in work.columns]
    if not group_cols:
        return pd.DataFrame()
    return work.groupby(group_cols, dropna=False).agg(
        advisory_market_hold=("advisory_market_hold", "first"),
        advisory_market_hold_pct=("advisory_market_hold_pct", "first"),
        advisory_market_completeness_status=("advisory_market_completeness_status", "first"),
        advisory_no_vig_available=("advisory_no_vig_available", "first"),
        advisory_no_vig_blocker_reason=("advisory_no_vig_blocker_reason", "first"),
        number_of_sides_detected=("_side", "nunique"),
    ).reset_index()


def line_shopping_summary(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty:
        return pd.DataFrame()
    out = _select_columns(frame, [
        "event", "market_type", "prediction", "advisory_current_decimal_odds", "sportsbook", "bookmaker", *SOURCE_COLUMNS, *MARKET_COMPLETENESS_COLUMNS,
        "advisory_best_available_decimal_odds", "advisory_best_available_sportsbook",
        "advisory_line_shopping_gain", "advisory_line_shopping_gain_pct", "advisory_best_price_EV",
    ])
    if "advisory_line_shopping_gain" in out.columns:
        out = out.sort_values("advisory_line_shopping_gain", ascending=False, na_position="last", ignore_index=True)
    return out


def stale_line_summary(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty or "advisory_stale_line_status" not in frame.columns:
        return pd.DataFrame()
    out = frame[frame["advisory_stale_line_status"].fillna("").astype(str).isin(STALE_WARNING_STATUSES)].copy()
    timestamp_cols = [col for col in [*ODDS_FRESHNESS_FIELDS, *EVENT_START_FIELDS] if col in out.columns]
    return _select_columns(out, ["event", "prediction", "market_type", "sportsbook", "bookmaker", *SOURCE_COLUMNS, *MARKET_COMPLETENESS_COLUMNS, "advisory_stale_line_status", "advisory_stale_line_reason", *timestamp_cols])


def duplicate_conflict_summary(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty:
        return pd.DataFrame()
    duplicate = frame.get("advisory_duplicate_event_status", pd.Series(index=frame.index, dtype=object)).fillna("UNIQUE_EVENT").astype(str)
    conflict = frame.get("advisory_conflict_status", pd.Series(index=frame.index, dtype=object)).fillna("NO_CONFLICT").astype(str)
    out = frame[(duplicate != "UNIQUE_EVENT") | (conflict != "NO_CONFLICT")].copy()
    return _select_columns(out, [
        "event", "prediction", "market_type", "sportsbook", "bookmaker", *SOURCE_COLUMNS, *MARKET_COMPLETENESS_COLUMNS,
        "advisory_duplicate_event_status", "advisory_duplicate_event_reason",
        "advisory_conflict_status", "advisory_conflict_reason", "advisory_playable_status",
    ])


def _values_equal(left: Any, right: Any) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    return str(left) == str(right)


def proof_safety_comparison(original_rows: Sequence[Mapping[str, Any]] | pd.DataFrame, advisory_output_rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> dict[str, Any]:
    original = _records(original_rows)
    advisory = _records(advisory_output_rows)
    violations: list[str] = []
    if len(original) != len(advisory):
        violations.append("row_count_changed")
    comparable = min(len(original), len(advisory))
    for idx in range(comparable):
        left = original[idx]
        right = advisory[idx]
        for field in IMMUTABLE_FIELDS:
            if field in left or field in right:
                if not _values_equal(left.get(field), right.get(field)):
                    violations.append(f"row_{idx}_{field}_changed")
    return {"passed": not violations, "violations": violations, "row_count_original": len(original), "row_count_advisory": len(advisory)}


def _iso(value: pd.Timestamp | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return value.isoformat()


def _parse_utc(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    try:
        parsed = pd.to_datetime(text, utc=True, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def _first_datetime_from_fields(row: Mapping[str, Any], fields: Sequence[str]) -> tuple[pd.Timestamp | None, str | None]:
    for field in fields:
        if field in row:
            parsed = _parse_utc(row.get(field))
            if parsed is not None:
                return parsed, field
    return None, None


def _detected_fields(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> list[str]:
    detected: list[str] = []
    for field in fields:
        if any(str(row.get(field, "")).strip() not in {"", "nan", "None", "NaT"} for row in rows if field in row):
            detected.append(field)
    return detected


def _field_has_numeric_value(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> bool:
    for row in rows:
        for field in fields:
            if field in row:
                value = pd.to_numeric(pd.Series([row.get(field)]), errors="coerce").iloc[0]
                if pd.notna(value):
                    return True
    return False


def _status_value(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_")


def _top_blocked_reason(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> dict[str, Any]:
    blocked = blocked_reason_summary(rows)
    if blocked.empty:
        return {"advisory_playable_status": None, "advisory_playable_reason": None, "row_count": 0}
    top = blocked.iloc[0].to_dict()
    return {
        "advisory_playable_status": top.get("advisory_playable_status"),
        "advisory_playable_reason": top.get("advisory_playable_reason"),
        "row_count": int(top.get("row_count") or 0),
    }


def advisory_real_file_diagnostics(rows: Sequence[Mapping[str, Any]] | pd.DataFrame, *, now: Any | None = None) -> dict[str, Any]:
    source = _records(rows)
    valued = advisory_rows(source)
    counts = advisory_summary_counts(valued)
    now_ts = _parse_utc(now) if now is not None else pd.Timestamp.now(tz="UTC")
    if now_ts is None:
        now_ts = pd.Timestamp.now(tz="UTC")
    event_times: list[pd.Timestamp] = []
    odds_times: list[pd.Timestamp] = []
    for row in valued:
        event_time, _event_field = _first_datetime_from_fields(row, EVENT_START_FIELDS)
        odds_time, _odds_field = _first_datetime_from_fields(row, ODDS_FRESHNESS_FIELDS)
        if event_time is not None:
            event_times.append(event_time)
        if odds_time is not None:
            odds_times.append(odds_time)
    earliest_event = min(event_times) if event_times else None
    latest_event = max(event_times) if event_times else None
    earliest_odds = min(odds_times) if odds_times else None
    latest_odds = max(odds_times) if odds_times else None
    historical_event_rows = int(sum(1 for item in event_times if item <= now_ts))
    future_event_rows = int(sum(1 for item in event_times if item > now_ts))
    total_event_times = len(event_times)
    if total_event_times == 0:
        slate_type = "UNKNOWN_EVENT_TIMES"
    elif future_event_rows == total_event_times:
        slate_type = "FUTURE_SLATE"
    elif historical_event_rows == total_event_times:
        slate_type = "HISTORICAL_ONLY"
    else:
        slate_type = "ACTIVE_OR_MIXED_SLATE"
    top = _top_blocked_reason(valued)
    no_playable_rows = bool(counts["total_advisory_rows"] > 0 and counts["PLAYABLE_PLUS_EV"] == 0 and counts["WATCHLIST_VALUE"] == 0 and counts["PREDICTION_ONLY_NOT_PLUS_EV"] == 0)
    all_blocked_by_past_events = bool(counts["total_advisory_rows"] > 0 and counts["blocked_rows"] == counts["total_advisory_rows"] and str(top.get("advisory_playable_reason") or "") == "event_start_time_is_not_future")
    if all_blocked_by_past_events:
        explanation = "All rows are blocked because event start times are not future. This file is being treated as historical/proof data, not a fresh playable slate."
        recommendation = "Upload a fresh future-event odds file to evaluate PLAYABLE_PLUS_EV rows."
    elif no_playable_rows:
        explanation = "No playable advisory rows were found. Review blocked reasons, market completeness, future event times, odds freshness, and sportsbook price sources."
        recommendation = "Upload a fresh future slate with current odds, complete market sides, and sportsbook/bookmaker prices."
    else:
        explanation = "The advisory engine produced at least one playable, watchlist, or prediction-only row."
        recommendation = "Review advisory tables before any manual promotion in a later phase."
    return {
        "section_title": "Why no playable +EV rows?",
        "total_rows": int(counts["total_advisory_rows"]),
        "playable_plus_ev_rows": int(counts["PLAYABLE_PLUS_EV"]),
        "watchlist_value_rows": int(counts["WATCHLIST_VALUE"]),
        "prediction_only_rows": int(counts["PREDICTION_ONLY_NOT_PLUS_EV"]),
        "blocked_rows": int(counts["blocked_rows"]),
        "complete_markets": int(counts["complete_markets"]),
        "incomplete_markets": int(counts["incomplete_markets"]),
        "top_blocked_status": top.get("advisory_playable_status"),
        "top_blocked_reason": top.get("advisory_playable_reason"),
        "top_blocked_row_count": int(top.get("row_count") or 0),
        "earliest_event_start_time": _iso(earliest_event),
        "latest_event_start_time": _iso(latest_event),
        "current_utc_time": _iso(now_ts),
        "file_slate_classification": slate_type,
        "historical_or_started_event_rows_with_event_time": historical_event_rows,
        "future_event_rows_with_event_time": future_event_rows,
        "event_start_fields_detected": _detected_fields(valued, EVENT_START_FIELDS),
        "odds_freshness_fields_detected": _detected_fields(valued, ODDS_FRESHNESS_FIELDS),
        "earliest_odds_timestamp": _iso(earliest_odds),
        "latest_odds_timestamp": _iso(latest_odds),
        "odds_freshness_timestamp_available_rows": int(len(odds_times)),
        "timestamp_rule_confirmation": "Event-start fields are used only for future/active/historical classification. Odds timestamp fields are used only for odds freshness.",
        "show_no_playable_warning": bool(no_playable_rows),
        "all_rows_blocked_by_non_future_events": all_blocked_by_past_events,
        "explanation": explanation,
        "recommended_next_action": recommendation,
        "playable_requirements": ["future event start times", "fresh odds timestamps", "complete same-sportsbook market sides", "current sportsbook/bookmaker prices", "valid model probability"],
        "proof_safety_check_result": proof_safety_comparison(source, valued),
    }


def _shadow_ready_status(rows: Sequence[Mapping[str, Any]]) -> str:
    detected = _detected_fields(rows, SHADOW_MODEL_FIELDS)
    if not detected:
        return "UNKNOWN"
    for row in rows:
        for field in ["lr_model_loaded", "model_loaded", "shadow_model_loaded"]:
            value = row.get(field)
            if isinstance(value, bool) and value:
                return "SHADOW_READY"
            if str(value).strip().lower() in {"true", "1", "yes", "loaded", "ready"}:
                return "SHADOW_READY"
        status = _status_value(row.get("shadow_model_status", ""))
        if status in {"ready", "shadow_ready", "loaded", "model_loaded"}:
            return "SHADOW_READY"
        model_source = _status_value(row.get("model_source", ""))
        if model_source and model_source not in {"no_lr_data", "no_model", "none", "unknown", "unchecked", "false"}:
            return "SHADOW_READY"
    if any(_status_value(row.get("shadow_model_status", "")) in {"needs_graded_results", "needs_more_rows"} for row in rows):
        return "NEEDS_GRADED_RESULTS"
    return "NO_MODEL_LOADED"


def _field_presence_summary(rows: Sequence[Mapping[str, Any]], valued: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "event_start_field_present": bool(_detected_fields(valued, EVENT_START_FIELDS)),
        "odds_freshness_field_present": bool(_detected_fields(valued, ODDS_FRESHNESS_FIELDS)),
        "sportsbook_field_present": bool(_detected_fields(valued, SPORTSBOOK_FIELDS)),
        "decimal_odds_field_present": bool(_detected_fields(valued, DECIMAL_ODDS_FIELDS)) and _field_has_numeric_value(valued, DECIMAL_ODDS_FIELDS),
        "model_probability_field_present": bool(_detected_fields(valued, MODEL_PROBABILITY_FIELDS)) and _field_has_numeric_value(valued, MODEL_PROBABILITY_FIELDS),
        "market_type_field_present": bool(_detected_fields(valued, MARKET_TYPE_FIELDS)),
        "prediction_selection_field_present": bool(_detected_fields(valued, PREDICTION_FIELDS)),
        "event_start_fields_detected": _detected_fields(valued, EVENT_START_FIELDS),
        "odds_freshness_fields_detected": _detected_fields(valued, ODDS_FRESHNESS_FIELDS),
        "sportsbook_fields_detected": _detected_fields(valued, SPORTSBOOK_FIELDS),
        "decimal_odds_fields_detected": _detected_fields(valued, DECIMAL_ODDS_FIELDS),
        "model_probability_fields_detected": _detected_fields(valued, MODEL_PROBABILITY_FIELDS),
        "market_type_fields_detected": _detected_fields(valued, MARKET_TYPE_FIELDS),
        "prediction_selection_fields_detected": _detected_fields(valued, PREDICTION_FIELDS),
    }


def fresh_slate_readiness_check(rows: Sequence[Mapping[str, Any]] | pd.DataFrame, *, now: Any | None = None, require_shadow_ready: bool = False) -> dict[str, Any]:
    source = _records(rows)
    valued = advisory_rows(source)
    counts = advisory_summary_counts(valued)
    diagnostics = advisory_real_file_diagnostics(valued, now=now)
    fields = _field_presence_summary(source, valued)
    source_counts = sportsbook_source_counts(valued)
    real_sportsbook_count = int(source_counts["real_sportsbook_count"])
    consensus_only_count = int(source_counts["consensus_only_count"])
    unknown_source_count = int(source_counts["unknown_source_count"])
    complete_market_count = int(counts["complete_markets"])
    incomplete_market_count = int(counts["incomplete_markets"])
    future_event_count = int(diagnostics["future_event_rows_with_event_time"])
    historical_or_started_event_count = int(diagnostics["historical_or_started_event_rows_with_event_time"])
    shadow_status = _shadow_ready_status(valued)
    passed_checks: list[str] = []
    failed_checks: list[str] = []
    warnings: list[str] = []
    score_breakdown = {
        "future_events_present": 20 if future_event_count > 0 else 0,
        "event_start_field_present": 10 if fields["event_start_field_present"] else 0,
        "odds_freshness_timestamp_present": 10 if fields["odds_freshness_field_present"] else 0,
        "real_sportsbook_bookmaker_present": 15 if real_sportsbook_count > 0 else 0,
        "decimal_odds_present": 10 if fields["decimal_odds_field_present"] else 0,
        "model_probability_present": 10 if fields["model_probability_field_present"] else 0,
        "market_type_present": 5 if fields["market_type_field_present"] else 0,
        "prediction_selection_present": 5 if fields["prediction_selection_field_present"] else 0,
        "complete_markets_present": 10 if complete_market_count > 0 else 0,
        "shadow_model_ready_or_not_required": 5 if (shadow_status == "SHADOW_READY" or not require_shadow_ready) else 0,
    }
    readiness_score = max(0, min(100, int(sum(score_breakdown.values()))))
    checks = {
        "future_events_present": future_event_count > 0,
        "event_start_field_present": bool(fields["event_start_field_present"]),
        "odds_freshness_timestamp_present": bool(fields["odds_freshness_field_present"]),
        "real_sportsbook_bookmaker_present": real_sportsbook_count > 0,
        "decimal_odds_present": bool(fields["decimal_odds_field_present"]),
        "model_probability_present": bool(fields["model_probability_field_present"]),
        "market_type_present": bool(fields["market_type_field_present"]),
        "prediction_selection_present": bool(fields["prediction_selection_field_present"]),
        "complete_markets_present": complete_market_count > 0,
        "shadow_ready_or_not_required": shadow_status == "SHADOW_READY" or not require_shadow_ready,
    }
    for name, passed in checks.items():
        (passed_checks if passed else failed_checks).append(name)
    critical_missing = [
        name for name in [
            "event_start_field_present", "odds_freshness_field_present", "sportsbook_field_present",
            "decimal_odds_field_present", "model_probability_field_present", "market_type_field_present",
            "prediction_selection_field_present",
        ] if not fields.get(name)
    ]
    if unknown_source_count and real_sportsbook_count == 0 and consensus_only_count == 0:
        warnings.append("Sportsbook source is missing or unknown. Add bookmaker/sportsbook/source fields.")
    if shadow_status != "SHADOW_READY":
        warnings.append("Shadow model is not ready. This is a warning unless Shadow readiness is required.")
    if consensus_only_count and real_sportsbook_count == 0:
        warnings.append("This file has only consensus/average prices. Consensus is useful for context, but it is not a real sportsbook.")
    if real_sportsbook_count == 1:
        warnings.append("Only one real sportsbook was detected. Line shopping needs at least two real books for comparison.")
    if real_sportsbook_count >= 2:
        warnings.append("Real sportsbook prices detected. Line shopping can compare available sportsbook prices when event, market, selection, and price fields align.")
    if incomplete_market_count and complete_market_count == 0:
        warnings.append("No complete same-sportsbook markets were detected for no-vig advisory review.")
    if critical_missing or (unknown_source_count > 0 and real_sportsbook_count == 0 and consensus_only_count == 0):
        readiness_status = "MISSING_CRITICAL_FIELDS"
        recommended_next_action = "This file is missing required fields for advisory value review. Add event times, odds timestamps, real sportsbook/bookmaker, decimal odds, model probability, market type, and prediction/selection."
    elif future_event_count == 0 and historical_or_started_event_count > 0:
        readiness_status = "HISTORICAL_ONLY"
        recommended_next_action = "This file is historical/proof-only. Upload a fresh future-event odds file for playable advisory +EV evaluation."
    elif real_sportsbook_count == 0 and consensus_only_count > 0:
        readiness_status = "NEEDS_REAL_SPORTSBOOK_PRICES"
        recommended_next_action = "This file has only consensus/average prices. Consensus is useful for context, but it is not a real sportsbook. Upload real sportsbook/bookmaker prices for playable line-shopping review."
    elif complete_market_count == 0:
        readiness_status = "NEEDS_COMPLETE_MARKETS"
        recommended_next_action = "This file needs complete same-sportsbook market sides before no-vig advisory value can be evaluated."
    elif require_shadow_ready and shadow_status != "SHADOW_READY":
        readiness_status = "NEEDS_SHADOW_TRAINING"
        recommended_next_action = "Shadow model is not loaded yet. Upload a graded CSV with finished results to train Shadow learning."
    elif readiness_score >= 85 and not any(name in failed_checks for name in ["future_events_present", "event_start_field_present", "decimal_odds_present", "model_probability_present"]):
        readiness_status = "READY_FOR_ADVISORY_VALUE"
        recommended_next_action = "This file is ready for advisory value scoring."
    else:
        readiness_status = "PARTIALLY_READY"
        recommended_next_action = "This file is partially ready. Review failed checks and warnings before relying on playable advisory +EV rows."
    return {
        "readiness_score": readiness_score,
        "readiness_score_breakdown": score_breakdown,
        "readiness_status": readiness_status,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "warnings": warnings,
        "recommended_next_action": recommended_next_action,
        "field_presence_summary": fields,
        "future_event_count": future_event_count,
        "historical_or_started_event_count": historical_or_started_event_count,
        "complete_market_count": complete_market_count,
        "incomplete_market_count": incomplete_market_count,
        "real_sportsbook_count": real_sportsbook_count,
        "consensus_only_count": consensus_only_count,
        "unknown_source_count": unknown_source_count,
        "shadow_readiness_status": shadow_status,
        "event_start_fields_detected": fields["event_start_fields_detected"],
        "odds_freshness_fields_detected": fields["odds_freshness_fields_detected"],
        "timestamp_rule_confirmation": diagnostics["timestamp_rule_confirmation"],
        "require_shadow_ready": bool(require_shadow_ready),
        "critical_missing_fields": critical_missing,
        "proof_safety_check_result": proof_safety_comparison(source, valued),
    }


def validate_advisory_rows(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> dict[str, Any]:
    original = _records(rows)
    valued = advisory_rows(original)
    frame = pd.DataFrame(valued)
    counts = advisory_summary_counts(valued)
    return {
        **counts,
        "total_rows": len(original),
        "advisory_rows_generated": len(valued),
        "rows_missing_odds": _safe_count(frame, "advisory_playable_status", BLOCKED_MISSING_ODDS),
        "rows_missing_model_probability": _safe_count(frame, "advisory_playable_status", BLOCKED_INVALID_PROBABILITY),
        "rows_blocked_by_reason": blocked_reason_summary(valued).to_dict("records"),
        "proof_safety_check_result": proof_safety_comparison(original, valued),
    }


def advisory_csv_frame(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty:
        return frame
    base_cols = [col for col in DISPLAY_KEY_COLUMNS if col in frame.columns]
    advisory_cols = [col for col in frame.columns if col.startswith("advisory_")]
    pass_through = [col for col in ["model_probability", "decimal_price", "decimal_odds", "odds_last_update", "event_start_utc"] if col in frame.columns]
    return frame[[*base_cols, *pass_through, *advisory_cols]].copy()


def advisory_report_text(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> str:
    valued = advisory_rows(rows)
    counts = advisory_summary_counts(valued)
    blocked = blocked_reason_summary(valued)
    diagnostics = advisory_real_file_diagnostics(valued)
    readiness = fresh_slate_readiness_check(valued)
    source_summary = sportsbook_source_summary(valued)
    market_summary = market_completeness_summary(valued)
    lines = [
        "Advisory Odds Value Report",
        "",
        "Fresh Slate Readiness",
        f"- Score: {readiness['readiness_score']}/100",
        f"- Status: {readiness['readiness_status']}",
        f"- Recommendation: {readiness['recommended_next_action']}",
        "",
        "Sportsbook Source Summary",
    ]
    if source_summary.empty:
        lines.append("- No sportsbook source rows detected.")
    else:
        for item in source_summary.to_dict("records"):
            lines.append(
                f"- {item.get('advisory_sportsbook_source_type')} / {item.get('advisory_normalized_sportsbook')}: "
                f"{item.get('row_count')} rows; counted for line shopping={item.get('counted_for_line_shopping')} — {item.get('reason')}"
            )
    lines.extend(["", "Market Completeness Summary"])
    if market_summary.empty:
        lines.append("- No market completeness rows detected.")
    else:
        for item in market_summary.head(20).to_dict("records"):
            lines.append(
                f"- {item.get('completeness_status')}: {item.get('row_count')} rows; "
                f"market={item.get('market_type')}; book={item.get('sportsbook_source')}; "
                f"line={item.get('line_value')}; no-vig={item.get('no_vig_available')} — {item.get('blocker_reason')}"
            )
    lines.extend([
        "",
        "Advisory +EV picks",
        f"- PLAYABLE_PLUS_EV: {counts['PLAYABLE_PLUS_EV']}",
        "",
        "Watchlist value picks",
        f"- WATCHLIST_VALUE: {counts['WATCHLIST_VALUE']}",
        "",
        "Prediction-only rows",
        f"- PREDICTION_ONLY_NOT_PLUS_EV: {counts['PREDICTION_ONLY_NOT_PLUS_EV']}",
        "",
        "Why no playable +EV rows?",
        f"- Top blocked reason: {diagnostics['top_blocked_reason']}",
        f"- Rows affected: {diagnostics['top_blocked_row_count']}",
        f"- File classification: {diagnostics['file_slate_classification']}",
        f"- Recommendation: {diagnostics['recommended_next_action']}",
        "",
        "Blocked reasons",
    ])
    if blocked.empty:
        lines.append("- No blocked advisory rows.")
    else:
        for item in blocked.to_dict("records"):
            lines.append(f"- {item.get('advisory_playable_status')}: {item.get('row_count')} rows — {item.get('advisory_playable_reason')}")
    lines.extend([
        "",
        "Best sportsbook prices",
        f"- Best-price opportunities: {counts['best_price_opportunities']}",
        "",
        "Stale-line warnings",
        f"- Stale rows: {counts['stale_rows']}",
        f"- Unknown freshness rows: {counts['unknown_freshness_rows']}",
        "",
        "Duplicate/conflict warnings",
        f"- Duplicate/conflict rows: {counts['duplicate_conflict_rows']}",
        "",
        "Safety confirmation",
        f"- {SAFETY_CONFIRMATION}",
        "- No bets were placed by this report.",
    ])
    return "\n".join(lines)

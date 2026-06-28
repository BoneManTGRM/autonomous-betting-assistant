from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.odds_value_engine import (
    ADVISORY_COLUMNS,
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
IMMUTABLE_FIELDS = [
    "model_probability",
    "model_probability_clean",
    "final_probability",
    "expected_value_per_unit",
    "EV",
    "ev",
    "official_EV",
    "official_ev",
    "model_edge",
    "model_market_edge",
    "edge",
    "official_edge",
    "lock_ready",
    "official_lock_ready",
    "publish_ready",
    "proof_hash",
    "proof_id",
    "locked_at_utc",
    "result",
    "grade",
    "outcome",
    "official_result",
    "final_result",
    "result_status",
    "pick_result",
    "settled_status",
]
DISPLAY_KEY_COLUMNS = ["event", "prediction", "sport", "league", "market_type", "sportsbook", "bookmaker"]


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
    if any("advisory_playable_status" in row for row in source):
        return source
    return build_advisory_odds_value_rows(source, config=config)


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
        "complete_markets": int((completeness == "COMPLETE_MARKET").sum()),
        "incomplete_markets": int((completeness == "INCOMPLETE_MARKET").sum()),
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
        "event", "prediction", "sport", "league", "market_type", "sportsbook", "bookmaker",
        "advisory_current_decimal_odds", "advisory_best_available_decimal_odds",
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
        "event", "prediction", "sport", "league", "market_type", "sportsbook", "bookmaker",
        "advisory_current_decimal_odds", "advisory_best_available_decimal_odds",
        "advisory_best_available_sportsbook", "advisory_raw_EV", "advisory_best_price_EV",
        "advisory_no_vig_edge", "advisory_market_completeness_status",
        "advisory_stale_line_status", "advisory_playable_reason",
    ])


def prediction_only_table(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty or "advisory_playable_status" not in frame.columns:
        return pd.DataFrame()
    out = frame[frame["advisory_playable_status"].fillna("").astype(str) == PREDICTION_ONLY_NOT_PLUS_EV].copy()
    return _select_columns(out, [
        "event", "prediction", "model_probability", "advisory_current_decimal_odds",
        "advisory_raw_EV", "advisory_no_vig_edge", "advisory_prediction_only_reason",
        "advisory_playable_reason",
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
    work["sportsbook_or_bookmaker"] = work.get("sportsbook", pd.Series(index=work.index, dtype=object)).fillna(work.get("bookmaker", pd.Series(index=work.index, dtype=object)))
    if "prediction" in work.columns:
        work["_side"] = work["prediction"].fillna("").astype(str)
    else:
        work["_side"] = ""
    group_cols = [col for col in ["event", "market_type", "sportsbook_or_bookmaker"] if col in work.columns]
    if not group_cols:
        return pd.DataFrame()
    agg = work.groupby(group_cols, dropna=False).agg(
        advisory_market_hold=("advisory_market_hold", "first"),
        advisory_market_hold_pct=("advisory_market_hold_pct", "first"),
        advisory_market_completeness_status=("advisory_market_completeness_status", "first"),
        number_of_sides_detected=("_side", "nunique"),
    ).reset_index()
    return agg


def line_shopping_summary(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty:
        return pd.DataFrame()
    out = _select_columns(frame, [
        "event", "market_type", "prediction", "advisory_current_decimal_odds", "sportsbook", "bookmaker",
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
    timestamp_cols = [col for col in ["odds_timestamp", "odds_last_update", "last_update", "pulled_at_utc", "created_at_utc", "event_start_time", "event_start_utc", "commence_time"] if col in out.columns]
    return _select_columns(out, ["event", "prediction", "market_type", "sportsbook", "bookmaker", "advisory_stale_line_status", "advisory_stale_line_reason", *timestamp_cols])


def duplicate_conflict_summary(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = advisory_frame(rows)
    if frame.empty:
        return pd.DataFrame()
    duplicate = frame.get("advisory_duplicate_event_status", pd.Series(index=frame.index, dtype=object)).fillna("UNIQUE_EVENT").astype(str)
    conflict = frame.get("advisory_conflict_status", pd.Series(index=frame.index, dtype=object)).fillna("NO_CONFLICT").astype(str)
    out = frame[(duplicate != "UNIQUE_EVENT") | (conflict != "NO_CONFLICT")].copy()
    return _select_columns(out, [
        "event", "prediction", "market_type", "sportsbook", "bookmaker",
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


def validate_advisory_rows(rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> dict[str, Any]:
    original = _records(rows)
    valued = advisory_rows(original)
    frame = pd.DataFrame(valued)
    counts = advisory_summary_counts(valued)
    status = frame.get("advisory_playable_status", pd.Series(dtype=str)).fillna("").astype(str) if not frame.empty else pd.Series(dtype=str)
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
    lines = [
        "Advisory Odds Value Report",
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
        "Blocked reasons",
    ]
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

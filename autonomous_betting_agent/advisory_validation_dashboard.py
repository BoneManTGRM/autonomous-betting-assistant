from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

VALIDATION_WIN = "WIN"
VALIDATION_LOSS = "LOSS"
VALIDATION_PUSH = "PUSH"
VALIDATION_CANCEL = "CANCEL"
VALIDATION_PENDING = "PENDING"
VALIDATION_UNKNOWN = "UNKNOWN"

WIN_VALUES = {"win", "won", "w", "correct", "hit", "graded_win", "1"}
LOSS_VALUES = {"loss", "lost", "l", "incorrect", "miss", "graded_loss", "0"}
PUSH_VALUES = {"push", "tie", "draw", "void_push", "graded_push"}
CANCEL_VALUES = {"cancel", "cancelled", "canceled", "void", "no_action", "postponed", "abandoned"}
PENDING_VALUES = {"pending", "open", "ungraded", "not_started", "in_progress", "live"}

RESULT_FIELDS = ["result", "grade", "outcome", "result_status", "pick_result", "final_result", "official_result", "status"]
ODDS_FIELDS = ["advisory_opening_decimal_odds", "advisory_current_decimal_odds", "decimal_odds", "odds_decimal", "odds"]
STAKE_FIELDS = ["advisory_stake_units", "stake_units", "risk_units", "stake", "units"]
EV_FIELDS = ["advisory_best_price_ev", "advisory_raw_ev", "expected_value", "ev"]
PROB_FIELDS = ["model_probability", "advisory_model_probability", "probability"]
CLV_FIELDS = ["advisory_clv_decimal_delta"]

VALIDATION_COLUMNS = [
    "advisory_validation_event_key",
    "advisory_validation_result_status",
    "advisory_validation_is_graded",
    "advisory_validation_is_usable",
    "advisory_validation_profit_units",
    "advisory_validation_roi_available",
    "advisory_validation_notes",
]


def _records(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows_or_frame is None:
        return []
    if isinstance(rows_or_frame, pd.DataFrame):
        return rows_or_frame.to_dict("records")
    return [deepcopy(dict(row)) for row in rows_or_frame if isinstance(row, Mapping)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "nan", "null", "nat", ""} else text


def _float(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        return float(text.replace("%", "").replace(",", ""))
    except ValueError:
        return None


def _first_float(row: Mapping[str, Any], fields: Sequence[str]) -> float | None:
    for field in fields:
        if field in row:
            parsed = _float(row.get(field))
            if parsed is not None:
                return parsed
    return None


def validation_event_key(row: Mapping[str, Any]) -> str:
    for field in ["event_id", "game_id", "match_id", "fixture_id", "advisory_event_id"]:
        value = _text(row.get(field))
        if value:
            return value
    event = _text(row.get("event") or row.get("event_name") or row.get("matchup") or row.get("game"))
    start = _text(row.get("event_start_utc") or row.get("start_time") or row.get("commence_time"))
    if event or start:
        return f"{event}|{start}"
    return "unknown_event"


def normalize_validation_result(row: Mapping[str, Any]) -> str:
    for field in RESULT_FIELDS:
        value = _text(row.get(field)).lower().replace(" ", "_").replace("-", "_")
        if not value:
            continue
        if value in WIN_VALUES:
            return VALIDATION_WIN
        if value in LOSS_VALUES:
            return VALIDATION_LOSS
        if value in PUSH_VALUES:
            return VALIDATION_PUSH
        if value in CANCEL_VALUES:
            return VALIDATION_CANCEL
        if value in PENDING_VALUES:
            return VALIDATION_PENDING
    return VALIDATION_UNKNOWN


def _profit_units(row: Mapping[str, Any], result_status: str) -> tuple[float | None, bool]:
    odds = _first_float(row, ODDS_FIELDS)
    stake = _first_float(row, STAKE_FIELDS)
    if odds is None or stake is None or odds <= 1 or stake <= 0:
        return None, False
    if result_status == VALIDATION_WIN:
        return round(stake * (odds - 1), 6), True
    if result_status == VALIDATION_LOSS:
        return round(-stake, 6), True
    if result_status in {VALIDATION_PUSH, VALIDATION_CANCEL}:
        return 0.0, True
    return None, False


def advisory_validation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    item = deepcopy(dict(row))
    status = normalize_validation_result(item)
    profit, roi_available = _profit_units(item, status)
    is_graded = status in {VALIDATION_WIN, VALIDATION_LOSS, VALIDATION_PUSH, VALIDATION_CANCEL}
    is_usable = status in {VALIDATION_WIN, VALIDATION_LOSS}
    notes = "Read-only validation row. Counts rows separately from unique events and does not change grading, proof, locks, bankroll, staking, or stored history."
    item.update({
        "advisory_validation_event_key": validation_event_key(item),
        "advisory_validation_result_status": status,
        "advisory_validation_is_graded": is_graded,
        "advisory_validation_is_usable": is_usable,
        "advisory_validation_profit_units": profit,
        "advisory_validation_roi_available": roi_available,
        "advisory_validation_notes": notes,
    })
    return item


def advisory_validation_rows(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> list[dict[str, Any]]:
    return [advisory_validation_row(row) for row in _records(rows_or_frame)]


def _summary_record(frame: pd.DataFrame, label: str, value: Any) -> dict[str, Any]:
    row_count = int(len(frame))
    unique_event_count = int(frame["advisory_validation_event_key"].nunique()) if "advisory_validation_event_key" in frame.columns else 0
    wins = int((frame["advisory_validation_result_status"] == VALIDATION_WIN).sum()) if not frame.empty else 0
    losses = int((frame["advisory_validation_result_status"] == VALIDATION_LOSS).sum()) if not frame.empty else 0
    pushes = int((frame["advisory_validation_result_status"] == VALIDATION_PUSH).sum()) if not frame.empty else 0
    cancels = int((frame["advisory_validation_result_status"] == VALIDATION_CANCEL).sum()) if not frame.empty else 0
    usable = wins + losses
    win_rate = round(wins / usable, 6) if usable else None
    stake_total = 0.0
    profit_total = 0.0
    roi_rows = 0
    for _, row in frame.iterrows():
        profit = _float(row.get("advisory_validation_profit_units"))
        stake = _first_float(row, STAKE_FIELDS)
        if profit is not None and stake is not None and stake > 0:
            profit_total += profit
            stake_total += stake
            roi_rows += 1
    roi_percent = round(profit_total / stake_total, 6) if stake_total > 0 else None
    return {
        label: value,
        "row_count": row_count,
        "unique_event_count": unique_event_count,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "cancels": cancels,
        "usable_graded_count": usable,
        "win_rate_excluding_push_cancel": win_rate,
        "roi_percent": roi_percent,
        "roi_rows": roi_rows,
        "average_odds": _safe_average(frame, ODDS_FIELDS),
        "average_model_probability": _safe_average(frame, PROB_FIELDS),
        "average_ev": _safe_average(frame, EV_FIELDS),
        "average_clv_decimal_delta": _safe_average(frame, CLV_FIELDS),
    }


def _safe_average(frame: pd.DataFrame, fields: Sequence[str]) -> float | None:
    values: list[float] = []
    for _, row in frame.iterrows():
        value = _first_float(row, fields)
        if value is not None:
            values.append(value)
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def advisory_validation_overall_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    rows = advisory_validation_rows(rows_or_frame)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["category", "row_count", "unique_event_count", "wins", "losses", "pushes", "cancels", "usable_graded_count", "win_rate_excluding_push_cancel", "roi_percent"])
    return pd.DataFrame([_summary_record(frame, "category", "overall")])


def advisory_validation_group_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, group_field: str) -> pd.DataFrame:
    rows = advisory_validation_rows(rows_or_frame)
    frame = pd.DataFrame(rows)
    if frame.empty or group_field not in frame.columns:
        return pd.DataFrame(columns=[group_field, "row_count", "unique_event_count", "wins", "losses", "pushes", "cancels", "usable_graded_count", "win_rate_excluding_push_cancel", "roi_percent"])
    records = []
    for value, part in frame.groupby(group_field, dropna=False):
        records.append(_summary_record(part.copy(), group_field, value))
    return pd.DataFrame(records).sort_values("row_count", ascending=False, ignore_index=True)


def advisory_validation_report_section(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> str:
    rows = advisory_validation_rows(rows_or_frame)
    if not rows:
        return "Advisory Performance Validation Dashboard\n- No rows available for read-only validation."
    overall = advisory_validation_overall_summary(rows).iloc[0].to_dict()
    by_status = advisory_validation_group_summary(rows, "advisory_calibrated_playable_status").head(8).to_dict("records")
    lines = [
        "Advisory Performance Validation Dashboard",
        "- Read-only local/session/upload analysis. Rows and unique events are counted separately.",
        f"- Rows: {overall.get('row_count')}; unique events: {overall.get('unique_event_count')}.",
        f"- Wins/Losses/Pushes/Cancels: {overall.get('wins')}/{overall.get('losses')}/{overall.get('pushes')}/{overall.get('cancels')}.",
        f"- Win rate excluding pushes/cancels: {overall.get('win_rate_excluding_push_cancel') if overall.get('win_rate_excluding_push_cancel') is not None else 'n/a'}.",
        f"- ROI percent when stake and odds exist: {overall.get('roi_percent') if overall.get('roi_percent') is not None else 'n/a'}.",
        "- Safety: read-only; no grading mutation, no proof mutation, no official lock change, no stake or bankroll action.",
    ]
    if by_status:
        lines.append("- By calibrated advisory status:")
        for item in by_status:
            lines.append(f"  - {item.get('advisory_calibrated_playable_status')}: rows={item.get('row_count')}; unique_events={item.get('unique_event_count')}; W-L={item.get('wins')}-{item.get('losses')}")
    return "\n".join(lines)

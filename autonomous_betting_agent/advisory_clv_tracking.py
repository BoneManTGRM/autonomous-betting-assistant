from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

CLV_POSITIVE = "CLV_POSITIVE"
CLV_NEGATIVE = "CLV_NEGATIVE"
CLV_NEUTRAL = "CLV_NEUTRAL"
CLV_MISSING_CLOSING_PRICE = "CLV_MISSING_CLOSING_PRICE"
CLV_INVALID_OPENING_PRICE = "CLV_INVALID_OPENING_PRICE"
CLV_INVALID_CLOSING_PRICE = "CLV_INVALID_CLOSING_PRICE"
CLV_NOT_APPLICABLE = "CLV_NOT_APPLICABLE"

OPENING_ODDS_FIELDS = [
    "advisory_opening_decimal_odds",
    "advisory_current_decimal_odds",
    "advisory_best_price_decimal_odds",
    "decimal_odds",
    "odds_decimal",
    "odds",
]

CLOSING_ODDS_FIELDS = [
    "advisory_closing_decimal_odds",
    "manual_closing_decimal_odds",
    "closing_decimal_odds",
    "closing_odds_decimal",
    "closing_odds",
    "final_decimal_odds",
]

CLV_COLUMNS = [
    "advisory_opening_decimal_odds",
    "advisory_closing_decimal_odds",
    "advisory_clv_decimal_delta",
    "advisory_clv_percent_delta",
    "advisory_clv_status",
    "advisory_clv_source",
    "advisory_clv_missing_reason",
    "advisory_clv_notes",
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
        parsed = float(text.replace("%", "").replace(",", ""))
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _first_price(row: Mapping[str, Any], fields: Sequence[str]) -> tuple[float | None, str]:
    for field in fields:
        if field in row:
            parsed = _float(row.get(field))
            if parsed is not None:
                return parsed, field
    return None, ""


def clv_diagnostics(row: Mapping[str, Any]) -> dict[str, Any]:
    opening, opening_source = _first_price(row, OPENING_ODDS_FIELDS)
    closing, closing_source = _first_price(row, CLOSING_ODDS_FIELDS)
    missing_reason = ""
    delta = None
    percent_delta = None
    if opening is None:
        status = CLV_INVALID_OPENING_PRICE
        missing_reason = "opening_decimal_odds_missing_or_invalid"
    elif closing is None:
        status = CLV_MISSING_CLOSING_PRICE if not any(field in row for field in CLOSING_ODDS_FIELDS) else CLV_INVALID_CLOSING_PRICE
        missing_reason = "closing_decimal_odds_missing_or_invalid"
    else:
        delta = round(opening - closing, 6)
        percent_delta = round(delta / closing, 6) if closing else None
        if abs(delta) < 0.000001:
            status = CLV_NEUTRAL
        elif delta > 0:
            status = CLV_POSITIVE
        else:
            status = CLV_NEGATIVE
    source = "manual_or_uploaded_closing_price_only"
    if opening_source or closing_source:
        source = f"manual_or_uploaded_only; opening_source={opening_source or 'missing'}; closing_source={closing_source or 'missing'}"
    notes = "CLV is calculated from uploaded/manual closing odds only. No odds polling, background worker, server, database, proof write, grading change, bankroll action, or stake action is performed. Positive CLV means the opening price was better than the closing price for the same selection."
    return {
        "advisory_opening_decimal_odds": opening,
        "advisory_closing_decimal_odds": closing,
        "advisory_clv_decimal_delta": delta,
        "advisory_clv_percent_delta": percent_delta,
        "advisory_clv_status": status,
        "advisory_clv_source": source,
        "advisory_clv_missing_reason": missing_reason,
        "advisory_clv_notes": notes,
    }


def apply_manual_clv_fields(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _records(rows_or_frame):
        item = deepcopy(row)
        item.update(clv_diagnostics(item))
        rows.append(item)
    return rows


def manual_clv_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    rows = apply_manual_clv_fields(rows_or_frame)
    if not rows:
        return pd.DataFrame(columns=["advisory_clv_status", "row_count", "average_clv_decimal_delta", "average_clv_percent_delta"])
    frame = pd.DataFrame(rows)
    grouped = frame.groupby("advisory_clv_status", dropna=False).agg(
        row_count=("advisory_clv_status", "size"),
        average_clv_decimal_delta=("advisory_clv_decimal_delta", "mean"),
        average_clv_percent_delta=("advisory_clv_percent_delta", "mean"),
    ).reset_index()
    return grouped.sort_values("row_count", ascending=False, ignore_index=True)


def manual_clv_group_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, group_field: str) -> pd.DataFrame:
    rows = apply_manual_clv_fields(rows_or_frame)
    if not rows:
        return pd.DataFrame(columns=[group_field, "row_count", "positive_clv_rows", "negative_clv_rows", "average_clv_decimal_delta"])
    frame = pd.DataFrame(rows)
    if group_field not in frame.columns:
        return pd.DataFrame(columns=[group_field, "row_count", "positive_clv_rows", "negative_clv_rows", "average_clv_decimal_delta"])
    grouped = frame.groupby(group_field, dropna=False).agg(
        row_count=(group_field, "size"),
        positive_clv_rows=("advisory_clv_status", lambda values: int((values == CLV_POSITIVE).sum())),
        negative_clv_rows=("advisory_clv_status", lambda values: int((values == CLV_NEGATIVE).sum())),
        average_clv_decimal_delta=("advisory_clv_decimal_delta", "mean"),
    ).reset_index()
    return grouped.sort_values("row_count", ascending=False, ignore_index=True)


def manual_clv_status_counts(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> dict[str, int]:
    counter = Counter(row.get("advisory_clv_status") for row in apply_manual_clv_fields(rows_or_frame))
    return {str(key): int(value) for key, value in counter.items() if key}


def manual_clv_report_section(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> str:
    rows = apply_manual_clv_fields(rows_or_frame)
    if not rows:
        return "Manual CLV Tracking\n- No rows available for manual CLV review."
    frame = pd.DataFrame(rows)
    counts = manual_clv_status_counts(frame)
    usable = frame[frame["advisory_clv_status"].isin([CLV_POSITIVE, CLV_NEGATIVE, CLV_NEUTRAL])]
    avg_delta = usable["advisory_clv_decimal_delta"].mean() if not usable.empty else None
    lines = [
        "Manual CLV Tracking",
        "- Source: uploaded/manual closing odds only.",
        f"- Positive CLV rows: {counts.get(CLV_POSITIVE, 0)}",
        f"- Negative CLV rows: {counts.get(CLV_NEGATIVE, 0)}",
        f"- Neutral CLV rows: {counts.get(CLV_NEUTRAL, 0)}",
        f"- Missing closing price rows: {counts.get(CLV_MISSING_CLOSING_PRICE, 0)}",
        f"- Average CLV decimal delta: {round(float(avg_delta), 6) if avg_delta is not None and pd.notna(avg_delta) else 'n/a'}",
        "- Safety: manual/upload-only; no odds polling, no server, no database, no proof mutation, no grading mutation, no stake or bankroll action.",
    ]
    return "\n".join(lines)

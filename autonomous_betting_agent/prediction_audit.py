from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .ara_filters import best_price, dedupe_ara_records, record_key
from .best_bets import apply_best_bet_layer

AUDIT_COLUMNS = [
    "aba_audit_record_key",
    "aba_audit_duplicate_count",
    "aba_audit_is_duplicate",
    "aba_audit_result_status",
    "aba_audit_unit_profit_loss",
]

FINISHED_RESULTS = {"won", "lost", "push", "void"}


@dataclass(frozen=True)
class PerformanceSummary:
    total_rows: int
    finished_rows: int
    wins: int
    losses: int
    pushes: int
    unit_profit_loss: float
    roi: float | None
    win_rate: float | None


def _result_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"win", "won", "w", "1", "true"}:
        return "won"
    if text in {"loss", "lost", "l", "0", "false"}:
        return "lost"
    if text in {"push", "void", "cancelled", "canceled", "refund"}:
        return "push"
    return "unknown"


def _unit_profit_loss(row: pd.Series) -> float | None:
    result = _result_status(row.get("result", row.get("outcome", row.get("graded_result"))))
    if result == "won":
        price = best_price(row.to_dict())
        return None if price is None else round(price - 1.0, 4)
    if result == "lost":
        return -1.0
    if result == "push":
        return 0.0
    return None


def _performance_summary(df: pd.DataFrame) -> PerformanceSummary:
    if df.empty:
        return PerformanceSummary(0, 0, 0, 0, 0, 0.0, None, None)
    statuses = df["aba_audit_result_status"] if "aba_audit_result_status" in df.columns else pd.Series(dtype="object")
    finished = df[statuses.isin(FINISHED_RESULTS)].copy()
    wins = int((finished["aba_audit_result_status"] == "won").sum()) if not finished.empty else 0
    losses = int((finished["aba_audit_result_status"] == "lost").sum()) if not finished.empty else 0
    pushes = int((finished["aba_audit_result_status"] == "push").sum()) if not finished.empty else 0
    settled = wins + losses
    profit = float(finished["aba_audit_unit_profit_loss"].dropna().sum()) if not finished.empty else 0.0
    risked = float(wins + losses)
    return PerformanceSummary(
        total_rows=int(len(df)),
        finished_rows=int(len(finished)),
        wins=wins,
        losses=losses,
        pushes=pushes,
        unit_profit_loss=round(profit, 4),
        roi=round(profit / risked, 4) if risked else None,
        win_rate=round(wins / settled, 4) if settled else None,
    )


def _counts(series: pd.Series) -> dict[str, int]:
    if series.empty:
        return {}
    return {str(key): int(value) for key, value in series.fillna("missing").value_counts(dropna=False).items()}


def audit_predictions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Apply final safety layers, mark duplicates, and summarize betting-system quality.

    Returns checked rows, deduped checked rows, and a JSON-serializable audit report.
    """
    checked = apply_best_bet_layer(df)
    if checked.empty:
        for column in AUDIT_COLUMNS:
            checked[column] = pd.Series(dtype="object")
        empty_summary = asdict(_performance_summary(checked))
        return checked, checked.copy(), {"raw": empty_summary, "deduped": empty_summary, "status_counts": {}, "risk_flag_counts": {}}

    keys = checked.apply(lambda row: record_key(row.to_dict()), axis=1)
    duplicate_counts = keys.map(keys.value_counts())
    checked["aba_audit_record_key"] = keys
    checked["aba_audit_duplicate_count"] = duplicate_counts.astype(int)
    checked["aba_audit_is_duplicate"] = duplicate_counts.gt(1)
    result_source = checked.get("result", checked.get("outcome", checked.get("graded_result", pd.Series(index=checked.index, dtype="object"))))
    checked["aba_audit_result_status"] = result_source.apply(_result_status)
    checked["aba_audit_unit_profit_loss"] = checked.apply(_unit_profit_loss, axis=1)

    deduped = dedupe_ara_records(checked)
    hard_rejects = checked[checked["aba_best_bet_status"].astype(str).eq("REJECT")]
    qualified = checked[checked["aba_best_bet_status"].astype(str).str.startswith("QUALIFIED", na=False)]

    all_flags: dict[str, int] = {}
    for column in ("ara_risk_flags", "ara_weather_flags", "aba_best_bet_reasons"):
        if column not in checked.columns:
            continue
        for value in checked[column].fillna(""):
            for flag in [item.strip() for item in str(value).split(";") if item.strip()]:
                all_flags[flag] = all_flags.get(flag, 0) + 1

    report = {
        "raw": asdict(_performance_summary(checked)),
        "deduped": asdict(_performance_summary(deduped)),
        "status_counts": _counts(checked["aba_best_bet_status"]),
        "grade_counts": _counts(checked["aba_best_bet_grade"]),
        "risk_flag_counts": dict(sorted(all_flags.items(), key=lambda item: (-item[1], item[0]))),
        "duplicate_rows": int(checked["aba_audit_is_duplicate"].sum()),
        "qualified_rows": int(len(qualified)),
        "rejected_rows": int(len(hard_rejects)),
    }
    return checked, deduped, report

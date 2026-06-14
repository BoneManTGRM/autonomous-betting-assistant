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
    "aba_audit_price_bucket",
]

FINISHED_RESULTS = {"won", "lost", "push", "void"}
PRICE_BUCKET_ORDER = [
    "missing",
    "under_1_10",
    "1_10_to_1_19",
    "1_20_to_1_29",
    "1_30_to_1_49",
    "1_50_to_1_99",
    "2_00_to_2_99",
    "3_00_plus",
]


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


def _price_bucket(row: pd.Series) -> str:
    price = best_price(row.to_dict())
    if price is None:
        return "missing"
    if price < 1.10:
        return "under_1_10"
    if price < 1.20:
        return "1_10_to_1_19"
    if price < 1.30:
        return "1_20_to_1_29"
    if price < 1.50:
        return "1_30_to_1_49"
    if price < 2.00:
        return "1_50_to_1_99"
    if price < 3.00:
        return "2_00_to_2_99"
    return "3_00_plus"


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


def _price_stats(df: pd.DataFrame) -> dict[str, float | int | None]:
    prices = df.apply(lambda row: best_price(row.to_dict()), axis=1).dropna() if not df.empty else pd.Series(dtype="float64")
    if prices.empty:
        return {
            "priced_rows": 0,
            "under_1_10_rows": 0,
            "under_1_20_rows": 0,
            "under_1_30_rows": 0,
            "min_price": None,
            "median_price": None,
            "max_price": None,
        }
    return {
        "priced_rows": int(len(prices)),
        "under_1_10_rows": int((prices < 1.10).sum()),
        "under_1_20_rows": int((prices < 1.20).sum()),
        "under_1_30_rows": int((prices < 1.30).sum()),
        "min_price": round(float(prices.min()), 4),
        "median_price": round(float(prices.median()), 4),
        "max_price": round(float(prices.max()), 4),
    }


def _bucket_performance(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if df.empty or "aba_audit_price_bucket" not in df.columns:
        return out
    for bucket in PRICE_BUCKET_ORDER:
        group = df[df["aba_audit_price_bucket"] == bucket]
        if group.empty:
            continue
        summary = asdict(_performance_summary(group))
        summary["rows"] = int(len(group))
        out[bucket] = summary
    return out


def audit_predictions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Apply final safety layers, mark duplicates, and summarize betting-system quality.

    Returns checked rows, deduped checked rows, and a JSON-serializable audit report.
    """
    checked = apply_best_bet_layer(df)
    if checked.empty:
        for column in AUDIT_COLUMNS:
            checked[column] = pd.Series(dtype="object")
        empty_summary = asdict(_performance_summary(checked))
        return checked, checked.copy(), {
            "raw": empty_summary,
            "deduped": empty_summary,
            "status_counts": {},
            "risk_flag_counts": {},
            "price_stats": _price_stats(checked),
            "price_bucket_performance_raw": {},
            "price_bucket_performance_deduped": {},
        }

    keys = checked.apply(lambda row: record_key(row.to_dict()), axis=1)
    duplicate_counts = keys.map(keys.value_counts())
    checked["aba_audit_record_key"] = keys
    checked["aba_audit_duplicate_count"] = duplicate_counts.astype(int)
    checked["aba_audit_is_duplicate"] = duplicate_counts.gt(1)
    result_source = checked.get("result", checked.get("outcome", checked.get("graded_result", pd.Series(index=checked.index, dtype="object"))))
    checked["aba_audit_result_status"] = result_source.apply(_result_status)
    checked["aba_audit_unit_profit_loss"] = checked.apply(_unit_profit_loss, axis=1)
    checked["aba_audit_price_bucket"] = checked.apply(_price_bucket, axis=1)

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
        "price_stats": _price_stats(checked),
        "price_bucket_counts": _counts(checked["aba_audit_price_bucket"]),
        "price_bucket_performance_raw": _bucket_performance(checked),
        "price_bucket_performance_deduped": _bucket_performance(deduped),
    }
    return checked, deduped, report

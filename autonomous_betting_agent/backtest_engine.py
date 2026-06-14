from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .profit_goal import ProfitGoalPolicy, review_profit_goal_rows

TIME_COLUMNS = ("pick_time", "entry_time", "created_at", "timestamp", "as_of")
START_COLUMNS = ("start", "start_time", "event_start", "date", "commence_time")
FEATURE_TIME_COLUMNS = ("feature_timestamp", "data_as_of", "stats_as_of", "weather_as_of", "odds_as_of")
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")
LEAKAGE_COLUMNS = (
    "actual_winner_as_feature",
    "final_score_as_feature",
    "postgame_rating",
    "closing_odds_as_model_input",
    "closing_line_value_as_model_input",
)


@dataclass(frozen=True)
class BacktestPolicy:
    train_fraction: float = 0.70
    min_train_rows: int = 20
    min_test_rows: int = 20
    profit_goal_min_finished: int = 50
    allow_missing_pick_time: bool = False
    allow_missing_event_start: bool = False
    allow_missing_feature_timestamp: bool = True


@dataclass(frozen=True)
class BacktestReport:
    status: str
    raw_rows: int
    usable_rows: int
    rejected_rows: int
    train_rows: int
    test_rows: int
    leakage_flags: dict[str, int]
    train_profit_status: str
    test_profit_status: str
    train_roi: float | None
    test_roi: float | None
    train_win_rate: float | None
    test_win_rate: float | None
    required_actions: list[str]
    notes: list[str]


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(str(key)): value for key, value in row.items()}


def _first(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    lookup = _lookup(row)
    for key in keys:
        value = lookup.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return ""


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _has_result(row: Mapping[str, Any]) -> bool:
    return bool(str(_first(row, RESULT_COLUMNS)).strip())


def audit_row_for_leakage(row: Mapping[str, Any], policy: BacktestPolicy = BacktestPolicy()) -> list[str]:
    flags: list[str] = []
    pick_time = parse_time(_first(row, TIME_COLUMNS))
    event_start = parse_time(_first(row, START_COLUMNS))
    feature_time = parse_time(_first(row, FEATURE_TIME_COLUMNS))

    if pick_time is None and not policy.allow_missing_pick_time:
        flags.append("missing_pick_time")
    if event_start is None and not policy.allow_missing_event_start:
        flags.append("missing_event_start")
    if pick_time is not None and event_start is not None and pick_time > event_start:
        flags.append("pick_after_event_start")
    if feature_time is None and not policy.allow_missing_feature_timestamp:
        flags.append("missing_feature_timestamp")
    if feature_time is not None and pick_time is not None and feature_time > pick_time:
        flags.append("feature_timestamp_after_pick_time")

    lookup = _lookup(row)
    for column in LEAKAGE_COLUMNS:
        value = lookup.get(_clean_key(column))
        if str(value or "").strip().lower() in {"1", "true", "yes", "y"}:
            flags.append(column)
    return flags


def _split_rows(rows: list[Mapping[str, Any]], policy: BacktestPolicy) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    sorted_rows = sorted(rows, key=lambda row: parse_time(_first(row, TIME_COLUMNS)) or datetime.min.replace(tzinfo=timezone.utc))
    split_at = max(1, min(len(sorted_rows) - 1, int(len(sorted_rows) * policy.train_fraction))) if len(sorted_rows) > 1 else len(sorted_rows)
    return sorted_rows[:split_at], sorted_rows[split_at:]


def run_backtest_rows(rows: list[Mapping[str, Any]], policy: BacktestPolicy = BacktestPolicy()) -> BacktestReport:
    usable: list[Mapping[str, Any]] = []
    leakage_counts: dict[str, int] = {}
    for row in rows:
        flags = audit_row_for_leakage(row, policy)
        if flags:
            for flag in flags:
                leakage_counts[flag] = leakage_counts.get(flag, 0) + 1
            continue
        if not _has_result(row):
            leakage_counts["missing_result"] = leakage_counts.get("missing_result", 0) + 1
            continue
        usable.append(row)

    train_rows, test_rows = _split_rows(usable, policy)
    train_policy = ProfitGoalPolicy(min_finished=policy.profit_goal_min_finished, require_positive_clv=False)
    test_policy = ProfitGoalPolicy(min_finished=policy.profit_goal_min_finished, require_positive_clv=False)
    train = review_profit_goal_rows(list(train_rows), policy=train_policy)
    test = review_profit_goal_rows(list(test_rows), policy=test_policy)

    actions: list[str] = []
    if len(train_rows) < policy.min_train_rows:
        actions.append(f"Add more historical rows: train split has {len(train_rows)}, needs at least {policy.min_train_rows}.")
    if len(test_rows) < policy.min_test_rows:
        actions.append(f"Add more untouched test rows: test split has {len(test_rows)}, needs at least {policy.min_test_rows}.")
    if leakage_counts:
        actions.append("Fix leakage or missing-time flags before trusting the backtest.")
    if test.roi is None or test.roi <= 0:
        actions.append("Test ROI is not positive; do not treat the strategy as proven.")

    status = "PASS"
    if leakage_counts or len(test_rows) < policy.min_test_rows or test.roi is None or test.roi <= 0:
        status = "WATCH"
    if any(key in leakage_counts for key in ("pick_after_event_start", "feature_timestamp_after_pick_time", "actual_winner_as_feature", "final_score_as_feature", "closing_odds_as_model_input", "closing_line_value_as_model_input")):
        status = "FAIL"

    return BacktestReport(
        status=status,
        raw_rows=len(rows),
        usable_rows=len(usable),
        rejected_rows=len(rows) - len(usable),
        train_rows=len(train_rows),
        test_rows=len(test_rows),
        leakage_flags=leakage_counts,
        train_profit_status=train.status,
        test_profit_status=test.status,
        train_roi=train.roi,
        test_roi=test.roi,
        train_win_rate=train.win_rate,
        test_win_rate=test.win_rate,
        required_actions=actions or ["No immediate action required beyond larger prospective testing."],
        notes=[
            "Rows with future feature timestamps or postgame flags are rejected before scoring.",
            "Train/test split is time ordered by pick_time.",
            "Closing odds and CLV may be evaluated, but must not be used as model-input columns.",
        ],
    )


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run_backtest_csv(path: str | Path, policy: BacktestPolicy = BacktestPolicy()) -> BacktestReport:
    return run_backtest_rows(read_csv_rows(path), policy=policy)


def write_report(report: BacktestReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")

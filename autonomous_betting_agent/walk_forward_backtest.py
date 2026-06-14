from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .accuracy_calibration import apply_calibration, brier_score
from .ensemble_agreement import apply_ensemble_scoring
from .profit_goal import parse_price, parse_result, unit_profit_loss

TIME_COLUMNS = ("pick_time", "entry_time", "created_at", "timestamp", "as_of", "start_time", "date")
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")
PRICE_COLUMNS = ("best_price", "entry_odds", "price", "odds", "decimal_odds")


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train_rows: int
    test_rows: int
    selected_rows: int
    wins: int
    losses: int
    pushes: int
    win_rate: float | None
    average_odds: float | None
    roi: float | None
    unit_profit_loss: float
    brier_score: float | None


@dataclass(frozen=True)
class WalkForwardReport:
    status: str
    raw_rows: int
    folds: int
    total_test_rows: int
    total_selected_rows: int
    aggregate_wins: int
    aggregate_losses: int
    aggregate_pushes: int
    aggregate_win_rate: float | None
    aggregate_roi: float | None
    average_fold_roi: float | None
    worst_fold_roi: float | None
    best_fold_roi: float | None
    max_losing_streak: int
    fold_reports: list[WalkForwardFold]
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


def parse_time(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _time(row: Mapping[str, Any]) -> datetime:
    return parse_time(_first(row, TIME_COLUMNS))


def _metrics(rows: list[Mapping[str, Any]]) -> tuple[int, int, int, float | None, float | None, float | None, float]:
    wins = losses = pushes = 0
    prices: list[float] = []
    profit = 0.0
    for row in rows:
        result = parse_result(_first(row, RESULT_COLUMNS))
        price = parse_price(_first(row, PRICE_COLUMNS))
        if price is not None:
            prices.append(price)
        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1
        elif result == "push":
            pushes += 1
        if result in {"win", "loss", "push"}:
            profit += unit_profit_loss(result, price)
    decisions = wins + losses
    win_rate = wins / decisions if decisions else None
    avg_odds = sum(prices) / len(prices) if prices else None
    roi = profit / decisions if decisions else None
    return wins, losses, pushes, win_rate, avg_odds, roi, profit


def _max_losing_streak(rows: list[Mapping[str, Any]]) -> int:
    streak = 0
    max_streak = 0
    for row in sorted(rows, key=_time):
        result = parse_result(_first(row, RESULT_COLUMNS))
        if result == "loss":
            streak += 1
            max_streak = max(max_streak, streak)
        elif result == "win":
            streak = 0
    return max_streak


def run_walk_forward_backtest_rows(
    rows: list[Mapping[str, Any]],
    *,
    train_size: int = 100,
    test_size: int = 25,
    step_size: int | None = None,
    min_selected_per_fold: int = 1,
) -> WalkForwardReport:
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = step_size or test_size
    ordered = sorted(rows, key=_time)
    folds: list[WalkForwardFold] = []
    selected_all: list[Mapping[str, Any]] = []
    fold_id = 0
    start = train_size
    while start < len(ordered):
        train = ordered[max(0, start - train_size):start]
        test = ordered[start:start + test_size]
        if not test:
            break
        calibrated_test, _ = apply_calibration(list(test), list(train))
        scored = apply_ensemble_scoring(calibrated_test)
        selected = [row for row in scored if row.get("ensemble_status") == "ACCEPT"]
        if len(selected) < min_selected_per_fold:
            selected = [row for row in scored if row.get("ensemble_status") in {"ACCEPT", "WATCH"}][:min_selected_per_fold]
        wins, losses, pushes, win_rate, avg_odds, roi, profit = _metrics(selected)
        folds.append(WalkForwardFold(
            fold=fold_id,
            train_rows=len(train),
            test_rows=len(test),
            selected_rows=len(selected),
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=None if win_rate is None else round(win_rate, 6),
            average_odds=None if avg_odds is None else round(avg_odds, 6),
            roi=None if roi is None else round(roi, 6),
            unit_profit_loss=round(profit, 6),
            brier_score=brier_score(selected),
        ))
        selected_all.extend(selected)
        fold_id += 1
        start += step

    wins, losses, pushes, win_rate, _, aggregate_roi, _ = _metrics(selected_all)
    fold_rois = [fold.roi for fold in folds if fold.roi is not None]
    actions: list[str] = []
    if not folds:
        actions.append("Add more historical rows to create at least one walk-forward fold.")
    if aggregate_roi is None or aggregate_roi <= 0:
        actions.append("Aggregate walk-forward ROI is not positive.")
    if len(selected_all) < max(25, min_selected_per_fold * max(1, len(folds))):
        actions.append("Walk-forward selected sample is still small; collect more finished picks.")
    status = "PASS"
    if actions:
        status = "WATCH"
    if not folds:
        status = "FAIL"

    return WalkForwardReport(
        status=status,
        raw_rows=len(rows),
        folds=len(folds),
        total_test_rows=sum(fold.test_rows for fold in folds),
        total_selected_rows=len(selected_all),
        aggregate_wins=wins,
        aggregate_losses=losses,
        aggregate_pushes=pushes,
        aggregate_win_rate=None if win_rate is None else round(win_rate, 6),
        aggregate_roi=None if aggregate_roi is None else round(aggregate_roi, 6),
        average_fold_roi=None if not fold_rois else round(sum(fold_rois) / len(fold_rois), 6),
        worst_fold_roi=None if not fold_rois else round(min(fold_rois), 6),
        best_fold_roi=None if not fold_rois else round(max(fold_rois), 6),
        max_losing_streak=_max_losing_streak(selected_all),
        fold_reports=folds,
        required_actions=actions or ["No immediate action required beyond larger prospective validation."],
        notes=[
            "Each fold trains calibration only on rows before the test block.",
            "Walk-forward testing is designed to reduce overfitting and cherry-picking risk.",
        ],
    )


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run_walk_forward_backtest_csv(path: str | Path, *, train_size: int = 100, test_size: int = 25, step_size: int | None = None, min_selected_per_fold: int = 1) -> WalkForwardReport:
    return run_walk_forward_backtest_rows(read_csv_rows(path), train_size=train_size, test_size=test_size, step_size=step_size, min_selected_per_fold=min_selected_per_fold)


def write_report(report: WalkForwardReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")

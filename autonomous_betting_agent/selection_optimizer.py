from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .profit_goal import parse_price, parse_result, unit_profit_loss

TIME_COLUMNS = ("pick_time", "entry_time", "created_at", "timestamp", "as_of")
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")
PRICE_COLUMNS = ("best_price", "entry_odds", "price", "odds", "decimal_odds", "sportsbook_odds")


@dataclass(frozen=True)
class SelectionRule:
    min_probability: float | None
    min_edge: float | None
    min_data_quality: float | None
    min_bookmaker_count: int | None
    min_odds: float | None
    max_odds: float | None


@dataclass(frozen=True)
class SelectionMetrics:
    rows: int
    wins: int
    losses: int
    pushes: int
    win_rate: float | None
    average_odds: float | None
    unit_profit_loss: float
    roi: float | None


@dataclass(frozen=True)
class SelectionOptimizerReport:
    status: str
    raw_rows: int
    train_rows: int
    test_rows: int
    best_rule: SelectionRule | None
    train_metrics: SelectionMetrics | None
    test_metrics: SelectionMetrics | None
    tested_rules: int
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


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _time(row: Mapping[str, Any]) -> datetime:
    text = str(_first(row, TIME_COLUMNS) or "").strip()
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


def _probability(row: Mapping[str, Any]) -> float | None:
    for key in ("calibrated_probability", "model_probability", "probability", "prop_blended_probability", "prop_model_probability"):
        value = _float(_first(row, (key,)))
        if value is not None:
            return value / 100.0 if value > 1.0 else value
    return None


def _edge(row: Mapping[str, Any]) -> float | None:
    for key in ("edge", "expected_value", "ev", "prop_implied_edge"):
        value = _float(_first(row, (key,)))
        if value is not None:
            return value / 100.0 if abs(value) > 1.0 else value
    return None


def _quality(row: Mapping[str, Any]) -> float | None:
    for key in ("data_quality", "prop_data_quality", "feature_data_quality", "bookmaker_count"):
        value = _float(_first(row, (key,)))
        if value is not None:
            return value
    return None


def _book_count(row: Mapping[str, Any]) -> int | None:
    value = _float(_first(row, ("bookmaker_count", "book_count", "books")))
    return None if value is None else int(value)


def _odds(row: Mapping[str, Any]) -> float | None:
    return parse_price(_first(row, PRICE_COLUMNS))


def _passes(row: Mapping[str, Any], rule: SelectionRule) -> bool:
    prob = _probability(row)
    edge = _edge(row)
    quality = _quality(row)
    books = _book_count(row)
    odds = _odds(row)
    if rule.min_probability is not None and (prob is None or prob < rule.min_probability):
        return False
    if rule.min_edge is not None and (edge is None or edge < rule.min_edge):
        return False
    if rule.min_data_quality is not None and (quality is None or quality < rule.min_data_quality):
        return False
    if rule.min_bookmaker_count is not None and (books is None or books < rule.min_bookmaker_count):
        return False
    if rule.min_odds is not None and (odds is None or odds < rule.min_odds):
        return False
    if rule.max_odds is not None and (odds is None or odds > rule.max_odds):
        return False
    return True


def _metrics(rows: list[Mapping[str, Any]]) -> SelectionMetrics:
    wins = losses = pushes = 0
    prices: list[float] = []
    profit = 0.0
    for row in rows:
        result = parse_result(_first(row, RESULT_COLUMNS))
        if result is None:
            continue
        price = _odds(row)
        if price is not None:
            prices.append(price)
        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1
        elif result == "push":
            pushes += 1
        profit += unit_profit_loss(result, price)
    decisions = wins + losses
    return SelectionMetrics(
        rows=len(rows),
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=None if decisions == 0 else round(wins / decisions, 4),
        average_odds=None if not prices else round(sum(prices) / len(prices), 4),
        unit_profit_loss=round(profit, 4),
        roi=None if decisions == 0 else round(profit / decisions, 4),
    )


def _candidate_rules() -> list[SelectionRule]:
    rules: list[SelectionRule] = []
    for min_prob in (None, 0.55, 0.60, 0.65, 0.70):
        for min_edge in (None, 0.02, 0.05, 0.08):
            for min_quality in (None, 60.0, 70.0, 80.0):
                for min_books in (None, 3, 5, 8):
                    rules.append(
                        SelectionRule(
                            min_probability=min_prob,
                            min_edge=min_edge,
                            min_data_quality=min_quality,
                            min_bookmaker_count=min_books,
                            min_odds=1.30,
                            max_odds=3.00,
                        )
                    )
    return rules


def _split(rows: list[Mapping[str, Any]], train_fraction: float) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    ordered = sorted(rows, key=_time)
    if len(ordered) <= 1:
        return ordered, []
    split_at = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    return ordered[:split_at], ordered[split_at:]


def optimize_selection_rows(rows: list[Mapping[str, Any]], *, train_fraction: float = 0.70, min_train_selected: int = 20, min_test_selected: int = 20) -> SelectionOptimizerReport:
    train_rows, test_rows = _split(rows, train_fraction)
    best_rule: SelectionRule | None = None
    best_train: SelectionMetrics | None = None
    tested = 0
    for rule in _candidate_rules():
        selected = [row for row in train_rows if _passes(row, rule)]
        if len(selected) < min_train_selected:
            continue
        metrics = _metrics(selected)
        tested += 1
        if metrics.roi is None:
            continue
        if best_train is None or (metrics.roi, metrics.win_rate or 0, metrics.rows) > (best_train.roi or -999, best_train.win_rate or 0, best_train.rows):
            best_rule = rule
            best_train = metrics

    if best_rule is None:
        return SelectionOptimizerReport(
            status="NO_RULE_FOUND",
            raw_rows=len(rows),
            train_rows=len(train_rows),
            test_rows=len(test_rows),
            best_rule=None,
            train_metrics=None,
            test_metrics=None,
            tested_rules=tested,
            required_actions=["Add more graded rows or loosen minimum selected-row requirements."],
            notes=["Rules are selected on the time-ordered training split only."],
        )

    test_selected = [row for row in test_rows if _passes(row, best_rule)]
    test_metrics = _metrics(test_selected)
    actions: list[str] = []
    status = "PASS"
    if len(test_selected) < min_test_selected:
        status = "WATCH"
        actions.append(f"Untouched test selection has {len(test_selected)} rows; collect at least {min_test_selected} before trusting optimizer.")
    if test_metrics.roi is None or test_metrics.roi <= 0:
        status = "WATCH"
        actions.append("Optimized rule did not produce positive ROI on untouched test rows.")
    if best_train.roi is not None and test_metrics.roi is not None and best_train.roi > 0 and test_metrics.roi < best_train.roi / 2:
        status = "WATCH"
        actions.append("Test ROI is much weaker than train ROI; possible overfitting.")

    return SelectionOptimizerReport(
        status=status,
        raw_rows=len(rows),
        train_rows=len(train_rows),
        test_rows=len(test_rows),
        best_rule=best_rule,
        train_metrics=best_train,
        test_metrics=test_metrics,
        tested_rules=tested,
        required_actions=actions or ["No immediate action required beyond larger prospective validation."],
        notes=[
            "Optimizer chooses rules on the training split only and reports untouched test metrics separately.",
            "Use as a filter-discovery tool, not as proof of future profit.",
        ],
    )


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def optimize_selection_csv(path: str | Path, *, train_fraction: float = 0.70, min_train_selected: int = 20, min_test_selected: int = 20) -> SelectionOptimizerReport:
    return optimize_selection_rows(read_csv_rows(path), train_fraction=train_fraction, min_train_selected=min_train_selected, min_test_selected=min_test_selected)


def write_report(report: SelectionOptimizerReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")

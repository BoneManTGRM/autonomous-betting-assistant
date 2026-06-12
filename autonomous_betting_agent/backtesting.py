from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable, List

from .market_math import brier_score


@dataclass(frozen=True)
class BacktestRow:
    event_name: str
    probability: float
    outcome: int
    closing_probability: float | None = None


@dataclass(frozen=True)
class BacktestSummary:
    events: int
    brier: float
    accuracy: float
    average_closing_line_delta: float | None


def summarize_backtest(rows: Iterable[BacktestRow]) -> BacktestSummary:
    data: List[BacktestRow] = list(rows)
    if not data:
        raise ValueError("Backtest requires at least one row")
    brier_values = [brier_score(row.probability, row.outcome) for row in data]
    accuracy_values = [
        1.0 if (row.probability >= 0.5) == bool(row.outcome) else 0.0
        for row in data
    ]
    deltas = [
        row.probability - row.closing_probability
        for row in data
        if row.closing_probability is not None
    ]
    return BacktestSummary(
        events=len(data),
        brier=mean(brier_values),
        accuracy=mean(accuracy_values),
        average_closing_line_delta=mean(deltas) if deltas else None,
    )

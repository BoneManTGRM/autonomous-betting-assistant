from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .profit_goal import parse_price, parse_result, unit_profit_loss

REASON_COLUMNS = ("do_not_bet_reason", "rejection_reason", "validation_errors", "lineup_do_not_bet_reason", "odds_quality_flags")
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")
PRICE_COLUMNS = ("best_price", "entry_odds", "price", "odds", "decimal_odds")


@dataclass(frozen=True)
class RejectionReasonStats:
    reason: str
    sample_size: int
    wins: int
    losses: int
    pushes: int
    win_rate: float | None
    roi: float | None
    unit_profit_loss: float
    filter_helpfulness_score: float


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lowered = {str(key).lower().replace(" ", "_").replace("-", "_"): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower().replace(" ", "_").replace("-", "_"))
        if value not in (None, ""):
            return value
    return ""


def rejection_reasons(row: Mapping[str, Any]) -> list[str]:
    raw: list[str] = []
    for column in REASON_COLUMNS:
        value = _first(row, (column,))
        if value:
            raw.extend(str(value).replace(",", ";").split(";"))
    cleaned = sorted({" ".join(item.strip().lower().split()) for item in raw if item.strip()})
    return cleaned or ["unspecified_rejection"]


def learn_from_rejections(rows: list[Mapping[str, Any]]) -> list[RejectionReasonStats]:
    buckets: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        action = str(_first(row, ("bankroll_action", "final_decision"))).strip().upper()
        if action and action not in {"REJECT", "NO_BET"}:
            continue
        for reason in rejection_reasons(row):
            buckets.setdefault(reason, []).append(row)

    stats: list[RejectionReasonStats] = []
    for reason, bucket in buckets.items():
        wins = losses = pushes = 0
        profit = 0.0
        decisions = 0
        for row in bucket:
            result = parse_result(_first(row, RESULT_COLUMNS))
            if result is None:
                continue
            price = parse_price(_first(row, PRICE_COLUMNS))
            profit += unit_profit_loss(result, price)
            if result == "win":
                wins += 1
                decisions += 1
            elif result == "loss":
                losses += 1
                decisions += 1
            elif result == "push":
                pushes += 1
        win_rate = wins / decisions if decisions else None
        roi = profit / decisions if decisions else None
        helpfulness = 0.0 if roi is None else round(max(-100.0, min(100.0, -roi * 100)), 4)
        stats.append(RejectionReasonStats(
            reason=reason,
            sample_size=len(bucket),
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=None if win_rate is None else round(win_rate, 6),
            roi=None if roi is None else round(roi, 6),
            unit_profit_loss=round(profit, 6),
            filter_helpfulness_score=helpfulness,
        ))
    return sorted(stats, key=lambda item: (item.filter_helpfulness_score, item.sample_size), reverse=True)


def add_filter_helpfulness(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    stats = {item.reason: item for item in learn_from_rejections(rows)}
    output: list[dict[str, Any]] = []
    for row in rows:
        out = dict(row)
        reason_scores = [stats[reason].filter_helpfulness_score for reason in rejection_reasons(row) if reason in stats]
        out["filter_helpfulness_score"] = "" if not reason_scores else str(round(max(reason_scores), 4))
        output.append(out)
    return output

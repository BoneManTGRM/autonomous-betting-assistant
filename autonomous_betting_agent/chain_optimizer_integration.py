"""Integration helpers for wiring Chain Optimizer v2 into Streamlit pages."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from autonomous_betting_agent.chain_optimizer_v2 import ChainOptimizerResult, optimize_chain_candidates


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _num(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _prob(row: Mapping[str, Any], *keys: str) -> float | None:
    value = _num(row, *keys)
    if value is None:
        return None
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _odds(row: Mapping[str, Any]) -> float | None:
    return _num(row, "decimal_odds", "decimal_price", "odds_at_pick", "best_price", "current_decimal_odds")


def _ev(row: Mapping[str, Any]) -> float:
    value = _num(row, "expected_value", "ev", "expected_value_per_unit", "profit_expected_value")
    return value if value is not None else -999.0


def _risk(row: Mapping[str, Any]) -> float:
    value = _num(row, "risk_score", "blended_risk_score", "combined_risk_score")
    return value if value is not None else 5.0


def _market(row: Mapping[str, Any]) -> str:
    return _text(row, "market", "market_type", "bet_type").lower()


def _selection(row: Mapping[str, Any]) -> str:
    return _text(row, "selection", "prediction", "pick", "exact_bet").lower()


def _game_key(row: Mapping[str, Any]) -> str:
    return _text(row, "game", "event", "event_name", "matchup") or "Unknown"


def _is_bad_straight_candidate(row: Mapping[str, Any]) -> bool:
    text = f"{_market(row)} {_selection(row)}"
    if "random" in text or "filler" in text:
        return True
    if "home run" in text or " homer" in text or " hr" in f" {text}":
        return True
    if "player" in text or "prop" in text:
        return True
    return _prob(row, "model_probability", "learned_model_probability", "probability") is None or _odds(row) is None


def _is_result_row(row: Mapping[str, Any]) -> bool:
    status = _text(row, "result_status", "status", "grade", "outcome").lower()
    return status in {"win", "loss", "push", "void", "cancel", "canceled", "cancelled"}


def select_best_straight_pick(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    candidates = [dict(row) for row in rows if not _is_bad_straight_candidate(row) and not _is_result_row(row)]
    if not candidates:
        return None
    market_bonus = {
        "moneyline": 0.12,
        "h2h": 0.12,
        "1x2": 0.12,
        "spread": 0.08,
        "spreads": 0.08,
        "total": 0.04,
        "totals": 0.04,
    }

    def score(row: Mapping[str, Any]) -> tuple[float, float, float, float]:
        market = _market(row)
        bonus = max((value for key, value in market_bonus.items() if key in market), default=0.0)
        return (_ev(row), _prob(row, "model_probability", "learned_model_probability", "probability") or 0.0, -_risk(row), bonus)

    return max(candidates, key=score)


def select_candidate_chain_legs(rows: Iterable[Mapping[str, Any]], straight_pick: Mapping[str, Any]) -> list[dict[str, Any]]:
    straight_market = _market(straight_pick)
    straight_selection = _selection(straight_pick)
    legs: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if item is straight_pick:
            continue
        if _is_result_row(item):
            continue
        if _prob(item, "model_probability", "learned_model_probability", "probability") is None or _odds(item) is None:
            continue
        if _market(item) == straight_market and _selection(item) == straight_selection:
            continue
        legs.append(item)
    return legs


def build_chain_optimizer_results(
    rows: Iterable[Mapping[str, Any]],
    *,
    target_payout: float | None = None,
    stake: float | None = None,
    external_context: Mapping[str, Any] | None = None,
    client_profile: Mapping[str, Any] | None = None,
) -> list[ChainOptimizerResult]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_game_key(row)].append(row)
    results: list[ChainOptimizerResult] = []
    for group_rows in grouped.values():
        straight = select_best_straight_pick(group_rows)
        if not straight:
            continue
        legs = select_candidate_chain_legs(group_rows, straight)
        if not legs:
            continue
        results.append(
            optimize_chain_candidates(
                straight,
                legs,
                target_payout=target_payout,
                stake=stake,
                external_context=external_context,
                client_profile=client_profile,
            )
        )
    return results


__all__ = [
    "select_best_straight_pick",
    "select_candidate_chain_legs",
    "build_chain_optimizer_results",
]

"""Odds value calculations for ABA Signal Pro.

This module is local-first and provider-agnostic. It works with rows from APIs,
CSV imports, or manually entered sportsbook lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable, Mapping

DOUBLE_MONEY_DECIMAL = 2.0


def _text(row: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


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


def american_to_decimal(american_odds: float | int | str | None) -> float | None:
    if american_odds in (None, ""):
        return None
    try:
        odds = float(american_odds)
    except (TypeError, ValueError):
        return None
    if odds == 0:
        return None
    return round(1 + odds / 100, 6) if odds > 0 else round(1 + 100 / abs(odds), 6)


def decimal_to_american(decimal_odds: float | int | str | None) -> int | None:
    if decimal_odds in (None, ""):
        return None
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    if odds <= 1:
        return None
    return int(round((odds - 1) * 100)) if odds >= 2 else int(round(-100 / (odds - 1)))


def decimal_to_fractional(decimal_odds: float | int | str | None, max_denominator: int = 100) -> str:
    if decimal_odds in (None, ""):
        return "N/A"
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return "N/A"
    if odds <= 1:
        return "N/A"
    fraction = Fraction(odds - 1).limit_denominator(max_denominator)
    return f"{fraction.numerator}/{fraction.denominator}"


def normalize_decimal_odds(row: Mapping[str, Any]) -> float | None:
    decimal = _num(row, "decimal_odds", "decimal_price", "current_decimal_odds", "odds_at_pick", "best_decimal_odds")
    if decimal is not None and decimal > 1:
        return decimal
    american = _num(row, "american_odds", "current_american_odds", "odds", "best_american_odds")
    return american_to_decimal(american)


def decimal_to_implied_probability(decimal_odds: float | int | str | None) -> float | None:
    if decimal_odds in (None, ""):
        return None
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    if odds <= 1:
        return None
    return 1 / odds


def fair_decimal_odds(model_probability: float | int | str | None) -> float | None:
    probability = normalize_probability(model_probability)
    if probability is None or probability <= 0:
        return None
    return 1 / probability


def minimum_playable_odds(model_probability: float | int | str | None, min_edge: float = 0.0) -> float | None:
    probability = normalize_probability(model_probability)
    if probability is None or probability <= 0:
        return None
    required_implied = max(0.000001, probability - min_edge)
    return 1 / required_implied


def expected_value(model_probability: float | int | str | None, decimal_odds: float | int | str | None) -> float | None:
    probability = normalize_probability(model_probability)
    if probability is None or decimal_odds in (None, ""):
        return None
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    if odds <= 1:
        return None
    return probability * odds - 1


def model_edge(model_probability: float | int | str | None, implied_probability: float | int | str | None) -> float | None:
    model = normalize_probability(model_probability)
    implied = normalize_probability(implied_probability)
    if model is None or implied is None:
        return None
    return model - implied


def normalize_probability(value: float | int | str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    if probability > 1:
        probability /= 100.0
    return max(0.0, min(1.0, probability))


def row_model_probability(row: Mapping[str, Any]) -> float | None:
    return _prob(row, "model_probability", "learned_model_probability", "probability", "projected_probability")


def row_implied_probability(row: Mapping[str, Any]) -> float | None:
    supplied = _prob(row, "implied_probability", "market_implied_probability")
    if supplied is not None:
        return supplied
    return decimal_to_implied_probability(normalize_decimal_odds(row))


def row_edge(row: Mapping[str, Any]) -> float | None:
    supplied = _num(row, "edge", "model_market_edge")
    if supplied is not None:
        return supplied / 100 if abs(supplied) > 1 else supplied
    return model_edge(row_model_probability(row), row_implied_probability(row))


def row_ev(row: Mapping[str, Any]) -> float | None:
    supplied = _num(row, "expected_value", "ev")
    if supplied is not None:
        return supplied
    return expected_value(row_model_probability(row), normalize_decimal_odds(row))


def near_double_money_score(decimal_odds: float | int | str | None) -> float | None:
    if decimal_odds in (None, ""):
        return None
    try:
        odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    return abs(odds - DOUBLE_MONEY_DECIMAL)


def is_near_double_money(decimal_odds: float | int | str | None, tolerance: float = 0.25) -> bool:
    score = near_double_money_score(decimal_odds)
    return bool(score is not None and score <= tolerance)


@dataclass(frozen=True)
class OddsValueResult:
    decimal_odds: float | None
    american_odds: int | None
    fractional_odds: str
    implied_probability: float | None
    model_probability: float | None
    edge: float | None
    expected_value: float | None
    fair_decimal_odds: float | None
    minimum_playable_odds: float | None
    sportsbook: str
    near_double_distance: float | None
    label: str
    reason: str


def analyze_odds_value(row: Mapping[str, Any], min_edge: float = 0.0) -> OddsValueResult:
    decimal = normalize_decimal_odds(row)
    model = row_model_probability(row)
    implied = row_implied_probability(row)
    edge = row_edge(row)
    ev = row_ev(row)
    fair = fair_decimal_odds(model)
    minimum = minimum_playable_odds(model, min_edge=min_edge)
    sportsbook = _text(row, "sportsbook_casino", "sportsbook", "bookmaker", "best_bookmaker", default="Best available")
    near_double = near_double_money_score(decimal)

    if model is None or decimal is None:
        label = "NO BET"
        reason = "Model probability or sportsbook odds are missing."
    elif ev is not None and ev > 0 and edge is not None and edge > min_edge:
        label = "GOOD READ, GOOD PRICE"
        reason = "Model probability is above market implied probability and EV is positive."
    elif model >= 0.65 and (ev is None or ev <= 0):
        label = "GOOD READ, BAD PRICE"
        reason = "The model likes the pick, but the current sportsbook price does not create value."
    elif near_double is not None and near_double <= 0.25 and (ev is None or ev <= 0):
        label = "BAD VALUE"
        reason = "The price is near double-money, but probability and EV do not support forcing the bet."
    else:
        label = "BAD VALUE"
        reason = "The available probability and odds do not create a positive value recommendation."

    return OddsValueResult(
        decimal_odds=decimal,
        american_odds=decimal_to_american(decimal),
        fractional_odds=decimal_to_fractional(decimal),
        implied_probability=implied,
        model_probability=model,
        edge=edge,
        expected_value=ev,
        fair_decimal_odds=fair,
        minimum_playable_odds=minimum,
        sportsbook=sportsbook,
        near_double_distance=near_double,
        label=label,
        reason=reason,
    )


def best_available_line(rows: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    valid = [row for row in rows if normalize_decimal_odds(row) is not None]
    if not valid:
        return None
    return max(valid, key=lambda row: normalize_decimal_odds(row) or 0)

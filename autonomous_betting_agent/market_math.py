from __future__ import annotations

from typing import Optional, Tuple


def implied_probability(price: Optional[float]) -> Optional[float]:
    if price is None:
        return None
    if price <= 1.0:
        raise ValueError("Price must be greater than 1.0")
    return 1.0 / price


def normalize_two_way_market(
    home_price: Optional[float], away_price: Optional[float]
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    home_raw = implied_probability(home_price)
    away_raw = implied_probability(away_price)
    if home_raw is None or away_raw is None:
        return None, None, None
    total = home_raw + away_raw
    if total <= 0.0:
        return None, None, None
    return home_raw / total, away_raw / total, total - 1.0


def unit_edge(probability: float, price: Optional[float]) -> Optional[float]:
    if price is None:
        return None
    if not 0.0 <= probability <= 1.0:
        raise ValueError("Probability must be between 0 and 1")
    if price <= 1.0:
        raise ValueError("Price must be greater than 1.0")
    return probability * price - 1.0


def brier_score(probability: float, outcome: int) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("Probability must be between 0 and 1")
    if outcome not in (0, 1):
        raise ValueError("Outcome must be 0 or 1")
    return (probability - float(outcome)) ** 2

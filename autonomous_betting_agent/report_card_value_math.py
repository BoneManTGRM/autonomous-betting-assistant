from __future__ import annotations

from typing import Any

import pandas as pd


def safe_float(value: Any) -> float | None:
    """Parse a numeric value without inventing or defaulting missing data."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    try:
        if pd.isna(parsed):
            return None
    except Exception:
        pass
    return parsed


def normalize_probability(value: Any) -> float | None:
    """Return a probability in 0..1 from either decimal probability or 0..100 percent input."""
    parsed = safe_float(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        parsed /= 100.0
    return parsed if 0.0 <= parsed <= 1.0 else None


def market_probability_from_decimal_odds(decimal_odds: Any) -> float | None:
    """Decimal odds break-even probability: 1 / decimal odds."""
    odds = safe_float(decimal_odds)
    if odds is None or odds <= 1.0:
        return None
    return 1.0 / odds


def probability_edge(model_probability: Any, decimal_odds: Any) -> float | None:
    """Difference between model probability and market break-even probability."""
    model_prob = normalize_probability(model_probability)
    market_prob = market_probability_from_decimal_odds(decimal_odds)
    if model_prob is None or market_prob is None:
        return None
    return model_prob - market_prob


def pct_label(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return '-'
    return f'{value * 100:+.1f}%' if signed else f'{value * 100:.1f}%'


def value_rating(edge: float | None, language: str = 'en') -> str:
    spanish = str(language).lower().startswith('es')
    if edge is None:
        return 'Sin dato' if spanish else 'Unknown'
    if edge >= 0.05:
        return 'Valor fuerte' if spanish else 'Strong Value'
    if edge >= 0.02:
        return 'Valor positivo' if spanish else 'Positive Value'
    if edge > -0.01:
        return 'Neutral'
    return 'Valor negativo' if spanish else 'Negative Value'

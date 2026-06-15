from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .audit import parse_float
from .row_normalizer import result_status


def wilson_interval(wins: int, total: int, z: float = 1.96) -> dict[str, float | None]:
    if total <= 0:
        return {'rate': None, 'lower': None, 'upper': None, 'confidence': 0.95}
    p = wins / total
    denom = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) / total + z**2 / (4 * total**2))) / denom
    return {'rate': round(p, 6), 'lower': round(max(0.0, center - margin), 6), 'upper': round(min(1.0, center + margin), 6), 'confidence': 0.95}


def american_to_decimal(american: float) -> float | None:
    if american == 0:
        return None
    if american > 0:
        return round(1 + american / 100.0, 6)
    return round(1 + 100.0 / abs(american), 6)


def decimal_to_american(decimal_price: float) -> float | None:
    if decimal_price <= 1.0:
        return None
    if decimal_price >= 2.0:
        return round((decimal_price - 1.0) * 100.0, 2)
    return round(-100.0 / (decimal_price - 1.0), 2)


def break_even_decimal(win_rate: float | None) -> float | None:
    if win_rate is None or win_rate <= 0:
        return None
    return round(1.0 / win_rate, 6)


def roi_at_decimal(win_rate: float | None, decimal_price: float) -> float | None:
    if win_rate is None or decimal_price <= 1.0:
        return None
    return round((win_rate * (decimal_price - 1.0)) - (1.0 - win_rate), 6)


def count_clean_results(frame: pd.DataFrame) -> dict[str, int]:
    if frame is None or frame.empty:
        return {'wins': 0, 'losses': 0, 'total': 0, 'voids': 0, 'pending': 0}
    wins = losses = voids = pending = 0
    for row in frame.to_dict(orient='records'):
        status = result_status(row)
        if status == 'win':
            wins += 1
        elif status == 'loss':
            losses += 1
        elif status == 'void':
            voids += 1
        else:
            pending += 1
    return {'wins': wins, 'losses': losses, 'total': wins + losses, 'voids': voids, 'pending': pending}


def roi_scenarios(wins: int, losses: int) -> pd.DataFrame:
    total = wins + losses
    interval = wilson_interval(wins, total)
    rates = [
        ('observed', interval['rate']),
        ('wilson_low_95', interval['lower']),
        ('wilson_high_95', interval['upper']),
    ]
    prices = [
        ('+100', 2.00),
        ('-110', american_to_decimal(-110) or 1.9091),
        ('-150', american_to_decimal(-150) or 1.6667),
        ('-200', american_to_decimal(-200) or 1.5),
        ('-300', american_to_decimal(-300) or 1.3333),
        ('-400', american_to_decimal(-400) or 1.25),
        ('-500', american_to_decimal(-500) or 1.2),
    ]
    rows: list[dict[str, Any]] = []
    for rate_name, rate in rates:
        for label, decimal_price in prices:
            roi = roi_at_decimal(rate, decimal_price) if rate is not None else None
            rows.append({
                'rate_case': rate_name,
                'win_rate': rate,
                'odds': label,
                'decimal_price': decimal_price,
                'roi_per_unit': roi,
                'profit_per_100_units': None if roi is None else round(roi * 100.0, 2),
            })
    return pd.DataFrame(rows)


def statistical_summary(frame: pd.DataFrame) -> dict[str, Any]:
    counts = count_clean_results(frame)
    interval = wilson_interval(counts['wins'], counts['total'])
    be_decimal = break_even_decimal(interval['rate']) if interval['rate'] is not None else None
    be_american = decimal_to_american(be_decimal) if be_decimal is not None else None
    return {
        **counts,
        'observed_win_rate': interval['rate'],
        'wilson_low_95': interval['lower'],
        'wilson_high_95': interval['upper'],
        'break_even_decimal_at_observed_rate': be_decimal,
        'break_even_american_at_observed_rate': be_american,
        'sample_warning': sample_warning(counts['total']),
    }


def sample_warning(total: int) -> str:
    if total < 25:
        return 'Very small sample. Treat as early signal only.'
    if total < 100:
        return 'Small sample. Useful for monitoring, not strong proof.'
    if total < 500:
        return 'Moderate sample. Start judging signal quality, but keep tracking ROI.'
    if total < 1000:
        return 'Serious sample. ROI and CLV matter more than win rate alone.'
    return 'Strong sample size. Continue monitoring ROI, CLV, and sport-by-sport stability.'

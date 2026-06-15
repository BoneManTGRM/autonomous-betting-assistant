from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float
from .row_normalizer import normalize_frame


def implied_probability(decimal_price: float | None) -> float | None:
    if decimal_price is None or decimal_price <= 1.0:
        return None
    return round(1.0 / decimal_price, 6)


def analyze_line_row(row: dict[str, Any]) -> dict[str, Any]:
    locked = parse_float(row.get('decimal_price'))
    closing = parse_float(row.get('closing_decimal_price'))
    if locked is None or locked <= 1.0:
        return {'line_status': 'missing_locked_price', 'line_value_decimal': None, 'line_value_probability': None, 'line_value_signal': 'unknown'}
    if closing is None or closing <= 1.0:
        return {'line_status': 'missing_closing_price', 'line_value_decimal': None, 'line_value_probability': None, 'line_value_signal': 'unknown'}
    locked_imp = implied_probability(locked)
    closing_imp = implied_probability(closing)
    decimal_edge = round(locked - closing, 6)
    probability_edge = None if locked_imp is None or closing_imp is None else round(closing_imp - locked_imp, 6)
    if decimal_edge > 0 and (probability_edge or 0) > 0:
        signal = 'positive'
    elif decimal_edge < 0 and (probability_edge or 0) < 0:
        signal = 'negative'
    else:
        signal = 'flat'
    return {
        'line_status': 'ready',
        'line_value_decimal': decimal_edge,
        'line_value_probability': probability_edge,
        'locked_implied_probability': locked_imp,
        'closing_implied_probability': closing_imp,
        'line_value_signal': signal,
    }


def build_line_movement_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    rows = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(analyze_line_row(row))
        rows.append(item)
    return pd.DataFrame(rows)


def line_movement_summary(frame: pd.DataFrame) -> dict[str, int]:
    movement = build_line_movement_frame(frame)
    if movement.empty:
        return {'rows': 0, 'ready': 0, 'positive': 0, 'negative': 0, 'flat': 0, 'missing': 0}
    status = movement['line_status'].fillna('').astype(str)
    signal = movement['line_value_signal'].fillna('').astype(str)
    return {
        'rows': int(len(movement)),
        'ready': int(status.eq('ready').sum()),
        'positive': int(signal.eq('positive').sum()),
        'negative': int(signal.eq('negative').sum()),
        'flat': int(signal.eq('flat').sum()),
        'missing': int(status.ne('ready').sum()),
    }

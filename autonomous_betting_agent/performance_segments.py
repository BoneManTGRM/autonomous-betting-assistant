from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float
from .row_normalizer import normalize_frame, result_status

SEGMENT_COLUMNS = [
    'sport',
    'market_type',
    'confidence_tier',
    'odds_source',
    'bookmaker',
    'model_version',
    'api_bundle_version',
]


def probability_bucket(value: Any) -> str:
    prob = parse_float(value)
    if prob is None:
        return 'missing'
    if prob > 1:
        prob = prob / 100.0
    if prob < 0.55:
        return '<55%'
    if prob < 0.60:
        return '55-60%'
    if prob < 0.65:
        return '60-65%'
    if prob < 0.70:
        return '65-70%'
    if prob < 0.80:
        return '70-80%'
    return '80%+'


def odds_bucket(value: Any) -> str:
    price = parse_float(value)
    if price is None or price <= 1:
        return 'missing'
    if price < 1.25:
        return '<1.25'
    if price < 1.50:
        return '1.25-1.49'
    if price < 1.75:
        return '1.50-1.74'
    if price < 2.00:
        return '1.75-1.99'
    if price < 3.00:
        return '2.00-2.99'
    return '3.00+'


def _segment_summary(data: pd.DataFrame, column: str) -> pd.DataFrame:
    if data.empty or column not in data.columns:
        return pd.DataFrame(columns=['segment_field', 'segment_value', 'rows', 'wins', 'losses', 'resolved', 'hit_rate', 'net_units', 'total_staked_units', 'roi_percent'])
    rows: list[dict[str, Any]] = []
    for value, group in data.groupby(column, dropna=False):
        statuses = [result_status(row) for row in group.to_dict(orient='records')]
        wins = statuses.count('win')
        losses = statuses.count('loss')
        resolved = wins + losses
        profit = pd.to_numeric(group.get('profit_units', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()
        stake = pd.to_numeric(group.get('stake_units', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()
        rows.append({
            'segment_field': column,
            'segment_value': str(value) if str(value).strip() else 'missing',
            'rows': int(len(group)),
            'wins': int(wins),
            'losses': int(losses),
            'resolved': int(resolved),
            'hit_rate': None if resolved == 0 else round(wins / resolved, 6),
            'net_units': round(float(profit), 6),
            'total_staked_units': round(float(stake), 6),
            'roi_percent': None if stake <= 0 else round(float(profit) / float(stake) * 100.0, 3),
        })
    return pd.DataFrame(rows).sort_values(['resolved', 'rows'], ascending=False)


def build_segment_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame).copy()
    data['probability_bucket'] = data.get('model_probability', pd.Series([''] * len(data))).apply(probability_bucket)
    data['odds_bucket'] = data.get('decimal_price', pd.Series([''] * len(data))).apply(odds_bucket)
    segment_fields = SEGMENT_COLUMNS + ['probability_bucket', 'odds_bucket']
    pieces = [_segment_summary(data, field) for field in segment_fields if field in data.columns]
    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, ignore_index=True)


def top_segments(frame: pd.DataFrame, *, min_resolved: int = 3, limit: int = 20) -> pd.DataFrame:
    segments = build_segment_frame(frame)
    if segments.empty:
        return segments
    filtered = segments[pd.to_numeric(segments['resolved'], errors='coerce').fillna(0) >= min_resolved].copy()
    if filtered.empty:
        filtered = segments.copy()
    return filtered.sort_values(['hit_rate', 'resolved'], ascending=False).head(limit)

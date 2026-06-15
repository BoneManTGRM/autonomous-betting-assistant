from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .audit import parse_float
from .row_normalizer import normalize_frame, result_status, safe_text


def _prob(value: Any) -> float | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    if parsed > 1:
        parsed /= 100.0
    if 0 < parsed < 1:
        return parsed
    return None


def _brier(prob: float, actual: int) -> float:
    return (prob - actual) ** 2


def _log_loss(prob: float, actual: int) -> float:
    clipped = max(0.001, min(0.999, prob))
    return -(actual * math.log(clipped) + (1 - actual) * math.log(1 - clipped))


def _sort_key(row: dict[str, Any]) -> str:
    for key in ['prediction_timestamp', 'event_start_utc', 'graded_at_utc']:
        text = safe_text(row.get(key))
        if text:
            return text
    return safe_text(row.get('event'))


def _segment_key(row: dict[str, Any]) -> str:
    return '|'.join([safe_text(row.get('sport')).lower(), safe_text(row.get('market_type')).lower(), safe_text(row.get('confidence_tier')).lower()])


def walk_forward_validate(frame: pd.DataFrame, *, min_train_rows: int = 10) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    rows = []
    for row in data.to_dict(orient='records'):
        status = result_status(row)
        if status not in {'win', 'loss'}:
            continue
        prob = _prob(row.get('model_probability'))
        if prob is None:
            continue
        item = dict(row)
        item['_actual'] = 1 if status == 'win' else 0
        item['_model_probability'] = prob
        item['_sort_key'] = _sort_key(row)
        item['_segment_key'] = _segment_key(row)
        rows.append(item)
    rows = sorted(rows, key=lambda item: item['_sort_key'])
    history: list[dict[str, Any]] = []
    output: list[dict[str, Any]] = []
    for row in rows:
        if len(history) < min_train_rows:
            history.append(row)
            continue
        global_rate = sum(item['_actual'] for item in history) / len(history)
        segment_history = [item for item in history if item['_segment_key'] == row['_segment_key']]
        if len(segment_history) >= 5:
            segment_rate = sum(item['_actual'] for item in segment_history) / len(segment_history)
            calibrated = round((row['_model_probability'] * 0.65) + (segment_rate * 0.25) + (global_rate * 0.10), 6)
            calibration_source = 'segment_plus_global'
        else:
            calibrated = round((row['_model_probability'] * 0.75) + (global_rate * 0.25), 6)
            calibration_source = 'global_only'
        actual = int(row['_actual'])
        locked_price = parse_float(row.get('decimal_price'))
        profit_units = None
        if locked_price is not None and locked_price > 1:
            profit_units = round((locked_price - 1.0) if actual == 1 else -1.0, 6)
        output.append({
            'event': row.get('event', ''),
            'sport': row.get('sport', ''),
            'market_type': row.get('market_type', ''),
            'prediction': row.get('prediction', ''),
            'actual': actual,
            'model_probability': row['_model_probability'],
            'walk_forward_probability': calibrated,
            'calibration_source': calibration_source,
            'brier_model': round(_brier(row['_model_probability'], actual), 6),
            'brier_walk_forward': round(_brier(calibrated, actual), 6),
            'log_loss_model': round(_log_loss(row['_model_probability'], actual), 6),
            'log_loss_walk_forward': round(_log_loss(calibrated, actual), 6),
            'profit_units': profit_units,
            'train_rows_before_pick': len(history),
            'segment_train_rows_before_pick': len(segment_history),
            'sort_key': row['_sort_key'],
        })
        history.append(row)
    return pd.DataFrame(output)


def walk_forward_summary(frame: pd.DataFrame, *, min_train_rows: int = 10) -> dict[str, Any]:
    results = walk_forward_validate(frame, min_train_rows=min_train_rows)
    if results.empty:
        return {'tested_rows': 0, 'avg_brier_model': None, 'avg_brier_walk_forward': None, 'avg_log_loss_model': None, 'avg_log_loss_walk_forward': None, 'net_units': 0.0}
    return {
        'tested_rows': int(len(results)),
        'avg_brier_model': round(float(pd.to_numeric(results['brier_model'], errors='coerce').fillna(0).mean()), 6),
        'avg_brier_walk_forward': round(float(pd.to_numeric(results['brier_walk_forward'], errors='coerce').fillna(0).mean()), 6),
        'avg_log_loss_model': round(float(pd.to_numeric(results['log_loss_model'], errors='coerce').fillna(0).mean()), 6),
        'avg_log_loss_walk_forward': round(float(pd.to_numeric(results['log_loss_walk_forward'], errors='coerce').fillna(0).mean()), 6),
        'net_units': round(float(pd.to_numeric(results['profit_units'], errors='coerce').fillna(0).sum()), 6),
    }

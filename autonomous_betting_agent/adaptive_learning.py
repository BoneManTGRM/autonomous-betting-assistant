from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'


def _clean(value: Any) -> str:
    return ' '.join(str(value or '').strip().lower().replace('-', ' ').replace('_', ' ').split())


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _probability_bucket(value: Any) -> str:
    p = _safe_float(value)
    if p is None:
        return 'unknown'
    if p > 1.0 and p <= 100.0:
        p /= 100.0
    if p < 0.50:
        return '<50%'
    if p < 0.58:
        return '50-58%'
    if p < 0.62:
        return '58-62%'
    if p < 0.66:
        return '62-66%'
    if p < 0.70:
        return '66-70%'
    if p < 0.75:
        return '70-75%'
    return '75%+'


def _edge_bucket(value: Any) -> str:
    edge = _safe_float(value)
    if edge is None:
        return 'unknown'
    if edge < -0.05:
        return '<-5%'
    if edge < -0.02:
        return '-5--2%'
    if edge < 0.0:
        return '-2-0%'
    if edge < 0.02:
        return '0-2%'
    if edge < 0.05:
        return '2-5%'
    return '5%+'


def _odds_bucket(value: Any) -> str:
    odds = _safe_float(value)
    if odds is None:
        return 'unknown'
    if odds < 1.30:
        return '<1.30'
    if odds < 1.60:
        return '1.30-1.59'
    if odds < 1.90:
        return '1.60-1.89'
    if odds < 2.25:
        return '1.90-2.24'
    if odds < 3.00:
        return '2.25-2.99'
    return '3.00+'


def _books_bucket(value: Any) -> str:
    books = _safe_float(value)
    if books is None:
        return 'unknown'
    if books <= 3:
        return '0-3'
    if books <= 10:
        return '4-10'
    if books <= 25:
        return '11-25'
    return '26+'


def _api_bucket(value: Any) -> str:
    coverage = _safe_float(value)
    if coverage is None:
        return 'unknown'
    if coverage > 1.0:
        coverage /= 100.0
    if coverage >= 0.99:
        return '100%'
    if coverage >= 0.66:
        return '66-99%'
    if coverage >= 0.33:
        return '33-65%'
    if coverage > 0:
        return '1-32%'
    return '0%'


def _row_features(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    sport = _clean(row.get('sport') or row.get('sport_key'))
    market = _clean(row.get('market_type') or row.get('market'))
    decision = _clean(row.get('agent_decision') or row.get('decision'))
    bookmaker = _clean(row.get('bookmaker') or row.get('best_bookmaker'))
    probability_bucket = _probability_bucket(row.get('model_probability_clean') or row.get('model_probability') or row.get('probability'))
    edge_bucket = _edge_bucket(row.get('model_market_edge') or row.get('model_edge'))
    odds_bucket = _odds_bucket(row.get('decimal_price') or row.get('best_price'))
    books_bucket = _books_bucket(row.get('books') or row.get('bookmaker_count'))
    api_bucket = _api_bucket(row.get('api_coverage_score'))
    features = [
        ('probability_bucket', probability_bucket),
        ('edge_bucket', edge_bucket),
        ('odds_bucket', odds_bucket),
        ('books_bucket', books_bucket),
        ('api_coverage_bucket', api_bucket),
    ]
    if sport:
        features.append(('sport', sport))
        features.append(('sport_probability_bucket', f'{sport}|{probability_bucket}'))
    if market:
        features.append(('market_type', market))
    if sport and market:
        features.append(('sport_market', f'{sport}|{market}'))
    if decision:
        features.append(('agent_decision', decision))
    if bookmaker:
        features.append(('bookmaker', bookmaker))
    return features


def _feature_key(area_type: str, value: str) -> str:
    return f'{area_type}:{value}'.lower()


def load_pattern_index(memory_path: str | Path = MEMORY_BANK_PATH) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(Path(memory_path).read_text(encoding='utf-8'))
    except Exception:
        return {}
    patterns = payload.get('patterns', [])
    index: dict[str, dict[str, Any]] = {}
    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        area_type = _clean(pattern.get('area_type') or pattern.get('memory_type'))
        group_value = _clean(pattern.get('group_value'))
        if not area_type or not group_value:
            continue
        index[_feature_key(area_type, group_value)] = pattern
    return index


def _pattern_adjustment(pattern: Mapping[str, Any]) -> tuple[float, str]:
    records = _safe_float(pattern.get('records')) or 0.0
    reliability = _safe_float(pattern.get('reliability')) or 0.0
    smoothed_edge = _safe_float(pattern.get('smoothed_edge'))
    roi = _safe_float(pattern.get('roi'))
    if smoothed_edge is None:
        smoothed_edge = _safe_float(pattern.get('actual_minus_predicted')) or 0.0
    sample_weight = min(1.0, math.log(records + 1.0) / math.log(101.0)) if records > 0 else 0.0
    trust = max(0.0, min(1.0, 0.55 * reliability + 0.45 * sample_weight))
    adjustment = float(smoothed_edge) * trust * 22.0
    if roi is not None:
        adjustment += max(-4.0, min(4.0, roi * 18.0)) * trust
    adjustment = max(-12.0, min(12.0, adjustment))
    action = 'boost' if adjustment > 1.25 else 'penalty' if adjustment < -1.25 else 'neutral'
    label = f"{pattern.get('area_type','pattern')}={pattern.get('group_value','')} {action} {adjustment:+.2f}"
    return adjustment, label


def apply_adaptive_learning(frame: pd.DataFrame, *, memory_path: str | Path = MEMORY_BANK_PATH) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    index = load_pattern_index(memory_path)
    if not index:
        out = frame.copy()
        out['learning_pattern_count'] = 0
        out['learning_adjustment_score'] = 0.0
        out['learned_agent_score'] = pd.to_numeric(out.get('agent_score'), errors='coerce').fillna(0.0)
        out['learning_notes'] = 'no_learning_memory_loaded'
        return out
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient='records'):
        row = dict(raw)
        adjustments: list[float] = []
        notes: list[str] = []
        matched = 0
        for area_type, value in _row_features(row):
            pattern = index.get(_feature_key(area_type, value))
            if not pattern:
                continue
            matched += 1
            adjustment, note = _pattern_adjustment(pattern)
            adjustments.append(adjustment)
            if abs(adjustment) >= 1.0:
                notes.append(note[:90])
        if adjustments:
            positive = sum(value for value in adjustments if value > 0)
            negative = sum(value for value in adjustments if value < 0)
            total = max(-18.0, min(18.0, positive * 0.65 + negative * 0.95))
        else:
            total = 0.0
        base_score = _safe_float(row.get('agent_score')) or 0.0
        base_prob = _safe_float(row.get('model_probability_clean') or row.get('model_probability')) or 0.0
        learned_score = max(0.0, min(100.0, base_score + total))
        learned_probability = max(0.01, min(0.99, base_prob + (total / 100.0) * 0.18)) if base_prob else base_prob
        row['learning_pattern_count'] = matched
        row['learning_adjustment_score'] = round(total, 3)
        row['learned_agent_score'] = round(learned_score, 3)
        row['learned_model_probability'] = round(learned_probability, 6) if learned_probability else ''
        row['learning_notes'] = '; '.join(notes[:5]) if notes else ('matched_neutral_patterns' if matched else 'no_matching_patterns')
        rows.append(row)
    return pd.DataFrame(rows)

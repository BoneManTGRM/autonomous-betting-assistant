from __future__ import annotations

import json
import math
from datetime import datetime, timezone
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


def _safe_datetime(value: Any) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def load_memory_payload(memory_path: str | Path = MEMORY_BANK_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(Path(memory_path).read_text(encoding='utf-8'))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_pattern_index(memory_path: str | Path = MEMORY_BANK_PATH) -> dict[str, dict[str, Any]]:
    payload = load_memory_payload(memory_path)
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


def _pattern_metrics(pattern: Mapping[str, Any]) -> dict[str, float]:
    records = _safe_float(pattern.get('records')) or 0.0
    effective_records = _safe_float(pattern.get('effective_records')) or records
    reliability = _safe_float(pattern.get('reliability')) or 0.0
    smoothed_edge = _safe_float(pattern.get('smoothed_edge'))
    if smoothed_edge is None:
        smoothed_edge = _safe_float(pattern.get('actual_minus_predicted')) or 0.0
    roi = _safe_float(pattern.get('roi'))
    profit_units = _safe_float(pattern.get('profit_units')) or 0.0
    avg_clv = _safe_float(pattern.get('avg_clv_percent'))
    beat_close_rate = _safe_float(pattern.get('beat_close_rate'))
    sample_weight = min(1.0, math.log(effective_records + 1.0) / math.log(101.0)) if effective_records > 0 else 0.0
    trust = max(0.0, min(1.0, 0.50 * reliability + 0.40 * sample_weight + 0.10 * min(1.0, max(0.0, records) / 75.0)))
    return {
        'records': records,
        'effective_records': effective_records,
        'reliability': reliability,
        'smoothed_edge': float(smoothed_edge or 0.0),
        'roi': float(roi) if roi is not None else 0.0,
        'roi_known': 1.0 if roi is not None else 0.0,
        'profit_units': profit_units,
        'avg_clv': float(avg_clv) if avg_clv is not None else 0.0,
        'clv_known': 1.0 if avg_clv is not None else 0.0,
        'beat_close_rate': float(beat_close_rate) if beat_close_rate is not None else 0.0,
        'beat_close_known': 1.0 if beat_close_rate is not None else 0.0,
        'trust': trust,
    }


def _pattern_adjustment(pattern: Mapping[str, Any]) -> tuple[float, str, bool, str]:
    metrics = _pattern_metrics(pattern)
    adjustment = metrics['smoothed_edge'] * metrics['trust'] * 22.0
    if metrics['roi_known']:
        adjustment += max(-4.0, min(4.0, metrics['roi'] * 18.0)) * metrics['trust']
    if metrics['clv_known']:
        adjustment += max(-2.0, min(2.0, metrics['avg_clv'] * 35.0)) * metrics['trust']
    if metrics['beat_close_known'] and metrics['records'] >= 20:
        adjustment += max(-1.5, min(1.5, (metrics['beat_close_rate'] - 0.50) * 3.0)) * metrics['trust']
    adjustment = max(-14.0, min(14.0, adjustment))
    hard_block = bool(
        metrics['records'] >= 50
        and metrics['effective_records'] >= 25
        and metrics['reliability'] >= 0.45
        and (
            metrics['smoothed_edge'] <= -0.06
            or (metrics['roi_known'] and metrics['roi'] <= -0.08)
            or metrics['profit_units'] <= -10.0
        )
    )
    action = 'block' if hard_block else 'boost' if adjustment > 1.25 else 'penalty' if adjustment < -1.25 else 'neutral'
    label = f"{pattern.get('area_type','pattern')}={pattern.get('group_value','')} {action} {adjustment:+.2f}"
    return adjustment, label, hard_block, action


def recommend_stake_units(*, learned_score: float, total_adjustment: float, blocked: bool, base_units: float = 0.10) -> float:
    if blocked or learned_score < 35:
        return 0.0
    if learned_score >= 78 and total_adjustment >= 4:
        return 1.0
    if learned_score >= 68 and total_adjustment >= 1:
        return 0.5
    if learned_score >= 55:
        return max(base_units, 0.25)
    return base_units


def learning_drift_summary(memory_path: str | Path = MEMORY_BANK_PATH) -> dict[str, Any]:
    payload = load_memory_payload(memory_path)
    rows = [row for row in payload.get('compact_rows', []) if isinstance(row, dict)]
    usable: list[dict[str, Any]] = []
    for row in rows:
        probability = _safe_float(row.get('probability'))
        outcome = _safe_float(row.get('outcome'))
        if probability is None or outcome is None:
            continue
        when = _safe_datetime(row.get('start')) or _safe_datetime(row.get('last_seen_utc')) or datetime.min.replace(tzinfo=timezone.utc)
        usable.append({'probability': probability, 'outcome': outcome, 'when': when})
    if len(usable) < 40:
        return {'status': 'not_enough_data', 'rows': len(usable), 'score_adjustment': 0.0, 'probability_adjustment': 0.0, 'note': 'drift_not_enough_data'}
    usable.sort(key=lambda item: item['when'])
    recent_size = max(20, min(150, len(usable) // 3))
    recent = usable[-recent_size:]
    all_pred = sum(row['probability'] for row in usable) / len(usable)
    all_hit = sum(row['outcome'] for row in usable) / len(usable)
    recent_pred = sum(row['probability'] for row in recent) / len(recent)
    recent_hit = sum(row['outcome'] for row in recent) / len(recent)
    all_edge = all_hit - all_pred
    recent_edge = recent_hit - recent_pred
    drift = recent_edge - all_edge
    score_adjustment = max(-3.0, min(3.0, drift * 20.0))
    probability_adjustment = max(-0.015, min(0.015, drift * 0.08))
    status = 'recent_improving' if drift > 0.035 else 'recent_declining' if drift < -0.035 else 'stable'
    return {
        'status': status,
        'rows': len(usable),
        'recent_rows': len(recent),
        'all_edge': round(all_edge, 6),
        'recent_edge': round(recent_edge, 6),
        'drift': round(drift, 6),
        'score_adjustment': round(score_adjustment, 3),
        'probability_adjustment': round(probability_adjustment, 6),
        'note': f'drift_{status}',
    }


def threshold_suggestions(memory_path: str | Path = MEMORY_BANK_PATH) -> dict[str, Any]:
    payload = load_memory_payload(memory_path)
    patterns = [row for row in payload.get('patterns', []) if isinstance(row, dict)]
    positive = []
    negative = []
    for pattern in patterns:
        metrics = _pattern_metrics(pattern)
        enriched = {**pattern, **metrics}
        if metrics['records'] >= 20 and (metrics['smoothed_edge'] > 0.025 or metrics['roi'] > 0.03 or metrics['avg_clv'] > 0.015):
            positive.append(enriched)
        if metrics['records'] >= 20 and (metrics['smoothed_edge'] < -0.035 or metrics['roi'] < -0.04 or metrics['avg_clv'] < -0.015):
            negative.append(enriched)
    positive.sort(key=lambda row: (float(row.get('roi', 0)), float(row.get('smoothed_edge', 0)), float(row.get('avg_clv', 0)), float(row.get('records', 0))), reverse=True)
    negative.sort(key=lambda row: (float(row.get('roi', 0)), float(row.get('smoothed_edge', 0)), float(row.get('avg_clv', 0))))
    drift = learning_drift_summary(memory_path)
    preferred_markets = [row.get('group_value') for row in positive if row.get('area_type') in {'market_type', 'sport_market'}][:8]
    avoid_patterns = [row.get('area') or f"{row.get('area_type')}={row.get('group_value')}" for row in negative[:8]]
    return {
        'preferred_markets': preferred_markets,
        'avoid_patterns': avoid_patterns,
        'positive_pattern_count': len(positive),
        'negative_pattern_count': len(negative),
        'recommended_min_learned_score': 55 if len(positive) < 10 else 60,
        'recommended_min_edge': 0.0 if len(positive) < 10 else 0.01,
        'drift_status': drift.get('status', 'unknown'),
        'drift_score_adjustment': drift.get('score_adjustment', 0.0),
    }


def apply_adaptive_learning(frame: pd.DataFrame, *, memory_path: str | Path = MEMORY_BANK_PATH) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    index = load_pattern_index(memory_path)
    drift = learning_drift_summary(memory_path)
    if not index:
        out = frame.copy()
        out['learning_pattern_count'] = 0
        out['learning_adjustment_score'] = 0.0
        out['learning_drift_adjustment'] = float(drift.get('score_adjustment', 0.0) or 0.0)
        out['learned_agent_score'] = pd.to_numeric(out.get('agent_score'), errors='coerce').fillna(0.0)
        out['learned_model_probability'] = pd.to_numeric(out.get('model_probability_clean', out.get('model_probability')), errors='coerce').fillna(0.0)
        out['learning_blocked'] = False
        out['learning_action'] = 'no_memory'
        out['recommended_stake_units'] = pd.to_numeric(out.get('recommended_stake_units'), errors='coerce').fillna(0.10)
        out['learning_notes'] = 'no_learning_memory_loaded'
        return out
    rows: list[dict[str, Any]] = []
    drift_score = float(drift.get('score_adjustment', 0.0) or 0.0)
    drift_probability = float(drift.get('probability_adjustment', 0.0) or 0.0)
    drift_note = str(drift.get('note', 'drift_unknown'))
    for raw in frame.to_dict(orient='records'):
        row = dict(raw)
        adjustments: list[float] = []
        notes: list[str] = []
        matched = 0
        blocked = False
        action_counts = {'boost': 0, 'penalty': 0, 'block': 0, 'neutral': 0}
        for area_type, value in _row_features(row):
            pattern = index.get(_feature_key(area_type, value))
            if not pattern:
                continue
            matched += 1
            adjustment, note, hard_block, action = _pattern_adjustment(pattern)
            adjustments.append(adjustment)
            action_counts[action] = action_counts.get(action, 0) + 1
            blocked = blocked or hard_block
            if abs(adjustment) >= 1.0 or hard_block:
                notes.append(note[:90])
        if adjustments:
            positive = sum(value for value in adjustments if value > 0)
            negative = sum(value for value in adjustments if value < 0)
            total = max(-20.0, min(20.0, positive * 0.65 + negative * 0.95))
        else:
            total = 0.0
        if blocked:
            total = min(total, -18.0)
        total_with_drift = max(-22.0, min(22.0, total + drift_score))
        base_score = _safe_float(row.get('agent_score')) or 0.0
        base_prob = _safe_float(row.get('model_probability_clean') or row.get('model_probability')) or 0.0
        learned_score = max(0.0, min(100.0, base_score + total_with_drift))
        learned_probability = max(0.01, min(0.99, base_prob + (total / 100.0) * 0.18 + drift_probability)) if base_prob else base_prob
        base_units = _safe_float(row.get('recommended_stake_units')) or 0.10
        if blocked:
            learning_action = 'block_or_review'
        elif action_counts['boost'] > action_counts['penalty']:
            learning_action = 'boost'
        elif action_counts['penalty'] > action_counts['boost']:
            learning_action = 'penalty'
        else:
            learning_action = 'watch'
        if abs(drift_score) >= 0.75:
            notes.append(drift_note)
        row['learning_pattern_count'] = matched
        row['learning_adjustment_score'] = round(total, 3)
        row['learning_drift_adjustment'] = round(drift_score, 3)
        row['learned_agent_score'] = round(learned_score, 3)
        row['learned_model_probability'] = round(learned_probability, 6) if learned_probability else ''
        row['learning_blocked'] = bool(blocked)
        row['learning_action'] = learning_action
        row['recommended_stake_units'] = recommend_stake_units(learned_score=learned_score, total_adjustment=total_with_drift, blocked=blocked, base_units=base_units)
        row['learning_notes'] = '; '.join(notes[:6]) if notes else ('matched_neutral_patterns' if matched else 'no_matching_patterns')
        rows.append(row)
    return pd.DataFrame(rows)


def learning_impact_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {'rows': 0, 'boosted': 0, 'penalized': 0, 'blocked': 0, 'avg_adjustment': 0.0, 'avg_drift_adjustment': 0.0}
    adjustment = pd.to_numeric(frame.get('learning_adjustment_score'), errors='coerce').fillna(0.0)
    drift = pd.to_numeric(frame.get('learning_drift_adjustment'), errors='coerce').fillna(0.0)
    blocked = frame.get('learning_blocked') if 'learning_blocked' in frame.columns else pd.Series(False, index=frame.index)
    return {
        'rows': int(len(frame)),
        'boosted': int((adjustment > 1.25).sum()),
        'penalized': int((adjustment < -1.25).sum()),
        'blocked': int(pd.Series(blocked).astype(bool).sum()),
        'avg_adjustment': round(float(adjustment.mean()), 3) if len(adjustment) else 0.0,
        'avg_drift_adjustment': round(float(drift.mean()), 3) if len(drift) else 0.0,
    }

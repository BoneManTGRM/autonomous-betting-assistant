from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float


def _status(row: dict[str, Any]) -> str:
    text = str(row.get('result_status') or row.get('result') or '').strip().lower()
    if text in {'win', 'won', 'w', 'correct', 'hit'}:
        return 'win'
    if text in {'loss', 'lost', 'l', 'incorrect', 'miss'}:
        return 'loss'
    return ''


def _prob(row: dict[str, Any]) -> float | None:
    for key in ['probability', 'model_probability', 'predicted_probability', 'confidence_probability']:
        value = parse_float(row.get(key))
        if value is None:
            continue
        if value > 1:
            value /= 100.0
        if 0 < value < 1:
            return value
    return None


def learning_memory_health(rows: list[dict[str, Any]] | pd.DataFrame) -> dict[str, Any]:
    if isinstance(rows, pd.DataFrame):
        data = rows.to_dict(orient='records')
    else:
        data = list(rows or [])
    resolved = [row for row in data if _status(row) in {'win', 'loss'}]
    wins = sum(1 for row in resolved if _status(row) == 'win')
    losses = sum(1 for row in resolved if _status(row) == 'loss')
    with_prob = sum(1 for row in resolved if _prob(row) is not None)
    sports = {str(row.get('sport', '')).strip().lower() for row in resolved if str(row.get('sport', '')).strip()}
    markets = {str(row.get('market_type', '')).strip().lower() for row in resolved if str(row.get('market_type', '')).strip()}

    score = 0.0
    notes: list[str] = []
    if len(resolved) >= 500:
        score += 35
        notes.append('large_sample')
    elif len(resolved) >= 100:
        score += 28
        notes.append('serious_sample')
    elif len(resolved) >= 25:
        score += 18
        notes.append('starter_sample')
    elif len(resolved) >= 5:
        score += 8
        notes.append('tiny_sample')
    else:
        notes.append('not_enough_resolved_rows')

    if resolved:
        prob_rate = with_prob / len(resolved)
        score += prob_rate * 25
        if prob_rate < 0.70:
            notes.append('needs_more_real_probabilities')
        else:
            notes.append('good_probability_coverage')

    if wins > 0 and losses > 0:
        score += 15
        notes.append('has_wins_and_losses')
    else:
        notes.append('class_balance_weak')

    if len(sports) >= 4:
        score += 10
        notes.append('multi_sport_memory')
    elif len(sports) >= 2:
        score += 6
        notes.append('some_sport_diversity')
    else:
        notes.append('limited_sport_diversity')

    if len(markets) >= 3:
        score += 10
        notes.append('multi_market_memory')
    elif len(markets) >= 1:
        score += 5
        notes.append('limited_market_diversity')

    if len(resolved) >= 100 and with_prob >= 80 and wins > 0 and losses > 0:
        tier = 'strong_learning_memory'
        action = 'train_and_use_for_calibration'
    elif len(resolved) >= 25 and with_prob >= 15:
        tier = 'usable_learning_memory'
        action = 'train_but_keep_sample_warning'
    elif len(resolved) >= 5:
        tier = 'rough_learning_memory'
        action = 'train_for_rough_patterns_only'
    else:
        tier = 'not_ready'
        action = 'collect_more_finished_results'

    return {
        'learning_health_score': round(max(0.0, min(100.0, score)), 2),
        'learning_health_tier': tier,
        'recommended_learning_action': action,
        'resolved_rows': int(len(resolved)),
        'wins': int(wins),
        'losses': int(losses),
        'real_probability_rows': int(with_prob),
        'sport_count': int(len(sports)),
        'market_count': int(len(markets)),
        'health_notes': ' | '.join(notes),
    }


def learning_health_frame(rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([learning_memory_health(rows)])

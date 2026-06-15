from __future__ import annotations

from typing import Any

import pandas as pd

from .agent_decision_engine import evaluate_row
from .row_normalizer import normalize_frame, result_status, safe_text

SPORT_RULES = {
    'tennis': {'min_edge': 0.030, 'strong_edge': 0.070, 'min_probability': 0.57},
    'soccer': {'min_edge': 0.050, 'strong_edge': 0.095, 'min_probability': 0.60},
    'basketball': {'min_edge': 0.040, 'strong_edge': 0.080, 'min_probability': 0.58},
    'baseball': {'min_edge': 0.045, 'strong_edge': 0.090, 'min_probability': 0.56},
    'football': {'min_edge': 0.045, 'strong_edge': 0.085, 'min_probability': 0.58},
    'default': {'min_edge': 0.040, 'strong_edge': 0.085, 'min_probability': 0.58},
}


def sport_key(value: Any) -> str:
    text = safe_text(value).lower()
    if 'tennis' in text or 'atp' in text or 'wta' in text:
        return 'tennis'
    if 'nfl' in text or 'american football' in text or 'ncaaf' in text:
        return 'football'
    if 'nba' in text or 'basketball' in text or 'ncaab' in text:
        return 'basketball'
    if 'mlb' in text or 'baseball' in text:
        return 'baseball'
    if 'soccer' in text or 'fifa' in text or 'liga' in text or 'premier' in text or text == 'football':
        return 'soccer'
    return 'default'


def segment_performance(frame: pd.DataFrame, sport: str, market_type: str = '') -> dict[str, Any]:
    if frame is None or frame.empty:
        return {'resolved_rows': 0, 'wins': 0, 'losses': 0, 'hit_rate': None}
    data = normalize_frame(frame)
    s_key = sport_key(sport)
    filtered = []
    market = safe_text(market_type).lower()
    for row in data.to_dict(orient='records'):
        if sport_key(row.get('sport')) != s_key:
            continue
        if market and market not in safe_text(row.get('market_type')).lower():
            continue
        status = result_status(row)
        if status in {'win', 'loss'}:
            filtered.append(status)
    wins = filtered.count('win')
    losses = filtered.count('loss')
    resolved = wins + losses
    return {'resolved_rows': resolved, 'wins': wins, 'losses': losses, 'hit_rate': None if resolved == 0 else round(wins / resolved, 6)}


def sport_specific_decision(row: dict[str, Any], history: pd.DataFrame | None = None) -> dict[str, Any]:
    key = sport_key(row.get('sport'))
    rules = SPORT_RULES.get(key, SPORT_RULES['default'])
    decision = evaluate_row(row, min_edge=rules['min_edge'], strong_edge=rules['strong_edge'])
    model_probability = decision.get('model_probability_clean')
    if model_probability is not None and model_probability < rules['min_probability'] and decision['agent_decision'] in {'play_strong', 'play_small'}:
        decision['decision_reasons'] = (decision.get('decision_reasons', '') + ' | below_sport_min_probability').strip(' |')
        decision['agent_decision'] = 'watch_only'
        decision['recommended_stake_units'] = 0.0
    perf = segment_performance(history if history is not None else pd.DataFrame(), row.get('sport'), row.get('market_type'))
    if perf['resolved_rows'] >= 20 and perf['hit_rate'] is not None and perf['hit_rate'] < 0.52 and decision['agent_decision'] in {'play_strong', 'play_small'}:
        decision['decision_reasons'] = (decision.get('decision_reasons', '') + ' | weak_historical_segment').strip(' |')
        decision['agent_decision'] = 'watch_only'
        decision['recommended_stake_units'] = 0.0
    decision.update({
        'sport_model_key': key,
        'sport_min_edge': rules['min_edge'],
        'sport_strong_edge': rules['strong_edge'],
        'sport_min_probability': rules['min_probability'],
        'sport_segment_resolved_rows': perf['resolved_rows'],
        'sport_segment_hit_rate': perf['hit_rate'],
    })
    return decision


def build_sport_specific_decisions(frame: pd.DataFrame, history: pd.DataFrame | None = None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    hist = history if history is not None else data
    rows: list[dict[str, Any]] = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(sport_specific_decision(row, hist))
        rows.append(item)
    return pd.DataFrame(rows)


def sport_model_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=['sport_model_key', 'rows', 'wins', 'losses', 'hit_rate'])
    data = normalize_frame(frame)
    data['sport_model_key'] = data.get('sport', pd.Series([''] * len(data))).apply(sport_key)
    rows: list[dict[str, Any]] = []
    for key, group in data.groupby('sport_model_key'):
        statuses = [result_status(row) for row in group.to_dict(orient='records')]
        wins = statuses.count('win')
        losses = statuses.count('loss')
        resolved = wins + losses
        rows.append({'sport_model_key': key, 'rows': int(len(group)), 'wins': wins, 'losses': losses, 'resolved': resolved, 'hit_rate': None if resolved == 0 else round(wins / resolved, 6)})
    return pd.DataFrame(rows).sort_values(['resolved', 'rows'], ascending=False)

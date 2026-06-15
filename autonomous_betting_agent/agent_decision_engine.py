from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float
from .line_movement import analyze_line_row
from .row_normalizer import normalize_frame, safe_text

MINIMUM_EDGE = 0.035
STRONG_EDGE = 0.075
HIGH_PROBABILITY = 0.62


def implied_probability(decimal_price: Any) -> float | None:
    price = parse_float(decimal_price)
    if price is None or price <= 1.0:
        return None
    return round(1.0 / price, 6)


def clean_probability(value: Any) -> float | None:
    prob = parse_float(value)
    if prob is None:
        return None
    if prob > 1.0:
        prob = prob / 100.0
    if 0.0 < prob < 1.0:
        return round(prob, 6)
    return None


def field_coverage_score(row: dict[str, Any]) -> float:
    fields = [
        'event',
        'sport',
        'market_type',
        'prediction',
        'model_probability',
        'decimal_price',
        'bookmaker',
        'odds_source',
        'prediction_timestamp',
        'event_start_utc',
    ]
    present = sum(1 for field in fields if safe_text(row.get(field)))
    return round(present / len(fields), 6)


def evaluate_row(row: dict[str, Any], *, min_edge: float = MINIMUM_EDGE, strong_edge: float = STRONG_EDGE) -> dict[str, Any]:
    model_prob = clean_probability(row.get('model_probability'))
    market_prob = implied_probability(row.get('decimal_price'))
    coverage = field_coverage_score(row)
    line = analyze_line_row(row)

    reasons: list[str] = []
    signals: list[str] = []

    if not safe_text(row.get('event')):
        reasons.append('missing_event')
    if not safe_text(row.get('prediction')):
        reasons.append('missing_prediction')
    if model_prob is None:
        reasons.append('missing_model_probability')
    if market_prob is None:
        reasons.append('missing_decimal_price')
    if not safe_text(row.get('bookmaker')):
        reasons.append('missing_bookmaker')
    if not safe_text(row.get('prediction_timestamp')):
        signals.append('not_locked_yet')
    if coverage < 0.70:
        reasons.append('low_field_coverage')

    edge = None if model_prob is None or market_prob is None else round(model_prob - market_prob, 6)
    if edge is not None:
        signals.append(f'edge={edge:.3f}')
        if edge < 0:
            reasons.append('negative_edge')
        elif edge < min_edge:
            reasons.append('edge_below_minimum')
        elif edge >= strong_edge:
            signals.append('strong_edge')
        else:
            signals.append('positive_edge')

    line_signal = line.get('line_value_signal', 'unknown')
    if line_signal == 'positive':
        signals.append('positive_line_movement')
    elif line_signal == 'negative':
        reasons.append('negative_line_movement')
    elif line.get('line_status') != 'ready':
        signals.append('line_movement_unavailable')

    if reasons and any(reason in reasons for reason in ['missing_event', 'missing_prediction', 'missing_model_probability', 'missing_decimal_price']):
        decision = 'review_needed'
    elif 'negative_edge' in reasons or 'low_field_coverage' in reasons:
        decision = 'no_action'
    elif 'edge_below_minimum' in reasons or 'negative_line_movement' in reasons:
        decision = 'watch_only'
    elif edge is not None and edge >= strong_edge and model_prob is not None and model_prob >= HIGH_PROBABILITY:
        decision = 'play_strong'
    elif edge is not None and edge >= min_edge:
        decision = 'play_small'
    else:
        decision = 'watch_only'

    score = 0.0
    if model_prob is not None:
        score += model_prob * 40.0
    if edge is not None:
        score += max(-0.10, min(0.15, edge)) * 250.0
    score += coverage * 20.0
    if line_signal == 'positive':
        score += 7.5
    elif line_signal == 'negative':
        score -= 7.5
    if decision == 'review_needed':
        score = min(score, 35.0)
    if decision == 'no_action':
        score = min(score, 45.0)

    return {
        'agent_decision': decision,
        'agent_score': round(max(0.0, min(100.0, score)), 3),
        'model_probability_clean': model_prob,
        'market_implied_probability': market_prob,
        'model_market_edge': edge,
        'field_coverage_score': coverage,
        'line_value_signal': line_signal,
        'decision_reasons': ' | '.join(reasons),
        'decision_signals': ' | '.join(signals),
    }


def build_agent_decisions(frame: pd.DataFrame, *, min_edge: float = MINIMUM_EDGE, strong_edge: float = STRONG_EDGE) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    rows: list[dict[str, Any]] = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(evaluate_row(row, min_edge=min_edge, strong_edge=strong_edge))
        rows.append(item)
    return pd.DataFrame(rows)


def agent_decision_summary(frame: pd.DataFrame) -> dict[str, Any]:
    decisions = build_agent_decisions(frame)
    if decisions.empty:
        return {'rows': 0, 'play_strong': 0, 'play_small': 0, 'watch_only': 0, 'no_action': 0, 'review_needed': 0, 'average_score': None}
    decision = decisions['agent_decision'].fillna('').astype(str)
    return {
        'rows': int(len(decisions)),
        'play_strong': int(decision.eq('play_strong').sum()),
        'play_small': int(decision.eq('play_small').sum()),
        'watch_only': int(decision.eq('watch_only').sum()),
        'no_action': int(decision.eq('no_action').sum()),
        'review_needed': int(decision.eq('review_needed').sum()),
        'average_score': round(float(pd.to_numeric(decisions['agent_score'], errors='coerce').fillna(0).mean()), 3),
    }

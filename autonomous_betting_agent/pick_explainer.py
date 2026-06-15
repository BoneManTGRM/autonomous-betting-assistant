from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float
from .data_health import data_health_score
from .line_movement import analyze_line_row
from .row_normalizer import normalize_frame, safe_text


def explain_pick_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_frame(pd.DataFrame([row])).iloc[0].to_dict()
    probability = parse_float(normalized.get('model_probability'))
    if probability is not None and probability > 1:
        probability = probability / 100.0
    price = parse_float(normalized.get('decimal_price'))
    ev = parse_float(normalized.get('computed_ev_decimal'))
    event = safe_text(normalized.get('event'))
    prediction = safe_text(normalized.get('prediction'))
    bookmaker = safe_text(normalized.get('bookmaker'))
    confidence = safe_text(normalized.get('confidence_tier'))
    decision = safe_text(normalized.get('decision'))
    line = analyze_line_row(normalized)
    health = data_health_score(pd.DataFrame([normalized]))

    positives: list[str] = []
    risks: list[str] = []

    if probability is not None:
        positives.append(f'Model probability available: {probability:.1%}.')
        if probability >= 0.70:
            positives.append('High model probability tier.')
        elif probability < 0.55:
            risks.append('Model probability is below 55%.')
    else:
        risks.append('Missing model_probability.')

    if price is not None and price > 1:
        positives.append(f'Decimal price captured: {price}.')
    else:
        risks.append('Missing usable decimal_price.')

    if ev is not None:
        positives.append(f'Estimated EV available: {ev}.')
        if ev <= 0:
            risks.append('Estimated EV is not positive.')
    else:
        risks.append('Missing computed_ev_decimal.')

    if bookmaker:
        positives.append(f'Book/source captured: {bookmaker}.')
    else:
        risks.append('Missing bookmaker/source.')

    if confidence:
        positives.append(f'Confidence tier: {confidence}.')
    if decision:
        positives.append(f'Decision label: {decision}.')

    if line.get('line_value_signal') == 'positive':
        positives.append('Line movement was positive versus closing price.')
    elif line.get('line_value_signal') == 'negative':
        risks.append('Line movement was negative versus closing price.')
    elif line.get('line_status') != 'ready':
        risks.append('Closing price unavailable, so line movement cannot be evaluated.')

    if health.get('score', 0) < 70:
        risks.append(f'Data health is low for this row: {health.get("score", 0):.0f}/100.')

    return {
        'event': event,
        'prediction': prediction,
        'explanation_summary': ' | '.join(positives[:4]) if positives else 'No strong positive explanation fields available.',
        'positive_signals': positives,
        'risk_flags': risks,
        'data_health_score': health.get('score', 0),
        'line_value_signal': line.get('line_value_signal', 'unknown'),
    }


def build_pick_explanations(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    rows = []
    for raw in data.to_dict(orient='records'):
        explanation = explain_pick_row(raw)
        rows.append({
            **raw,
            'explanation_summary': explanation['explanation_summary'],
            'positive_signal_count': len(explanation['positive_signals']),
            'risk_flag_count': len(explanation['risk_flags']),
            'positive_signals': ' | '.join(explanation['positive_signals']),
            'risk_flags': ' | '.join(explanation['risk_flags']),
            'explanation_data_health_score': explanation['data_health_score'],
            'explanation_line_value_signal': explanation['line_value_signal'],
        })
    return pd.DataFrame(rows)

from pathlib import Path

import pandas as pd
import streamlit as st

import autonomous_betting_agent.adaptive_learning as adaptive_learning

_original_number_input = st.number_input
_original_apply_adaptive_learning = adaptive_learning.apply_adaptive_learning


def volume_number_input(label, *args, **kwargs):
    text = str(label)
    if text.startswith('Max large-list') or text.startswith('Máximo de filas'):
        kwargs['max_value'] = 1000
        kwargs['value'] = 700
    elif text.startswith('Minimum model probability') or text.startswith('Probabilidad mínima'):
        kwargs['value'] = 0.50
    elif text.startswith('Large-list min learned score') or text.startswith('Puntaje aprendido mínimo'):
        kwargs['value'] = 45.0
    return _original_number_input(label, *args, **kwargs)


def _num(frame: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(default, index=frame.index, dtype='float64')
    return pd.to_numeric(frame[col], errors='coerce').fillna(default)


def _pattern_tier(score: float) -> str:
    if score >= 85:
        return 'A+ Pattern Lock'
    if score >= 75:
        return 'A High Confidence'
    if score >= 65:
        return 'B Strong Pattern'
    if score >= 55:
        return 'C Research Edge'
    return 'D Review Only'


def _pattern_label(probability: float, score: float, patterns: float, adjustment: float) -> str:
    if probability < 0.58 and score >= 65 and patterns >= 2 and adjustment > 0:
        return 'low_confidence_pattern_edge'
    if score >= 75:
        return 'high_confidence_pattern_edge'
    if score >= 55:
        return 'research_pattern_edge'
    return 'no_pattern_edge'


def apply_volume_pattern_points(frame, *args, **kwargs):
    out = _original_apply_adaptive_learning(frame, *args, **kwargs)
    if out is None or out.empty:
        return out
    out = out.copy()
    prob = _num(out, 'learned_model_probability', 0.0)
    prob = prob.where(prob <= 1.0, prob / 100.0)
    base_score = _num(out, 'learned_agent_score', 0.0)
    adjust = _num(out, 'learning_adjustment_score', 0.0)
    patterns = _num(out, 'learning_pattern_count', 0.0)
    edge = _num(out, 'model_market_edge', 0.0)
    signal = _num(out, 'scanner_strength_score', 0.0)
    books = _num(out, 'books', 0.0).where(_num(out, 'books', 0.0).gt(0), _num(out, 'bookmaker_count', 0.0))
    odds = _num(out, 'decimal_price', 0.0)

    odds_band_bonus = pd.Series(0.0, index=out.index)
    odds_band_bonus += odds.between(1.30, 1.89, inclusive='both').astype(float) * 8.0
    odds_band_bonus += odds.between(1.90, 2.24, inclusive='both').astype(float) * 4.0
    odds_band_bonus -= odds.ge(3.00).astype(float) * 15.0
    odds_band_bonus -= odds.le(1.05).astype(float) * 10.0

    book_bonus = books.clip(0, 10) * 0.8
    pattern_bonus = patterns.clip(0, 5) * 4.0 + adjust.clip(-12, 12) * 1.4
    edge_bonus = edge.clip(-0.08, 0.12) * 130.0
    signal_bonus = signal.clip(0, 100) * 0.12
    probability_bonus = prob.clip(0, 1) * 25.0

    audit_penalty = pd.Series(0.0, index=out.index)
    if 'odds_audit_status' in out.columns:
        audit_penalty = out['odds_audit_status'].astype(str).str.lower().ne('pass').astype(float) * 30.0

    pattern_score = (base_score * 0.35 + probability_bonus + edge_bonus + signal_bonus + book_bonus + odds_band_bonus + pattern_bonus - audit_penalty).clip(0, 100).round(3)
    out['pattern_points'] = pattern_score
    out['pattern_confidence_tier'] = pattern_score.map(_pattern_tier)
    out['pattern_edge_label'] = [
        _pattern_label(float(prob.iloc[i]), float(pattern_score.iloc[i]), float(patterns.iloc[i]), float(adjust.iloc[i]))
        for i in range(len(out))
    ]
    out['pattern_high_confidence'] = pattern_score.ge(75)
    out['low_confidence_pattern_candidate'] = (prob.lt(0.58) & pattern_score.ge(65) & patterns.ge(2) & adjust.gt(0))
    if 'decision_signals' in out.columns:
        out['decision_signals'] = out['decision_signals'].astype(str) + '; pattern_points_v1'
    return out


adaptive_learning.apply_adaptive_learning = apply_volume_pattern_points
st.number_input = volume_number_input
code = Path(__file__).with_name('pro_predictor.py').read_text(encoding='utf-8')
exec(code, globals())

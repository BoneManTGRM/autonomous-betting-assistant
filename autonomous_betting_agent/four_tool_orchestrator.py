from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float
from .row_normalizer import normalize_frame, safe_text

REQUIRED_FOR_SCANNER_HANDOFF = ['event', 'sport', 'market_type', 'prediction', 'decimal_price', 'bookmaker']
REQUIRED_FOR_PREDICTOR_HANDOFF = ['event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price', 'event_start_utc']
REQUIRED_FOR_VALUE_HANDOFF = ['event', 'prediction', 'model_probability', 'decimal_price', 'agent_decision']
REQUIRED_FOR_LEARNING_HANDOFF = ['event', 'prediction', 'result_status']


def _present_rate(frame: pd.DataFrame, columns: list[str]) -> float:
    if frame is None or frame.empty or not columns:
        return 0.0
    available = [column for column in columns if column in frame.columns]
    if not available:
        return 0.0
    rates = []
    for column in available:
        rates.append(frame[column].map(lambda value: bool(safe_text(value))).mean())
    missing_columns_penalty = len(available) / len(columns)
    return round(float(sum(rates) / len(rates)) * missing_columns_penalty, 6)


def _count(frame: pd.DataFrame, column: str, value: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].astype(str).str.lower().eq(value.lower()).sum())


def _numeric_mean(frame: pd.DataFrame, column: str) -> float | None:
    if frame is None or frame.empty or column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors='coerce').dropna()
    if values.empty:
        return None
    return round(float(values.mean()), 6)


def _resolved_count(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    for column in ['result_status', 'result', 'outcome']:
        if column in frame.columns:
            values = frame[column].astype(str).str.lower().str.strip()
            return int(values.isin(['win', 'won', 'loss', 'lost', '1', '0', '1.0', '0.0']).sum())
    return 0


def _missing_columns(frame: pd.DataFrame, required: list[str]) -> list[str]:
    if frame is None or frame.empty:
        return list(required)
    return [column for column in required if column not in frame.columns or not frame[column].map(lambda value: bool(safe_text(value))).any()]


def page_health(frame: pd.DataFrame | list[dict[str, Any]], *, page: str) -> dict[str, Any]:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    rows = int(len(normalized)) if normalized is not None else 0
    page_key = page.strip().lower().replace(' ', '_')

    scanner_coverage = _present_rate(normalized, REQUIRED_FOR_SCANNER_HANDOFF)
    predictor_coverage = _present_rate(normalized, REQUIRED_FOR_PREDICTOR_HANDOFF)
    value_coverage = _present_rate(normalized, REQUIRED_FOR_VALUE_HANDOFF)
    learning_coverage = _present_rate(normalized, REQUIRED_FOR_LEARNING_HANDOFF)
    resolved = _resolved_count(normalized)
    avg_agent_score = _numeric_mean(normalized, 'agent_score')
    avg_scanner_strength = _numeric_mean(normalized, 'scanner_strength_score')
    playable = _count(normalized, 'agent_decision', 'play_strong') + _count(normalized, 'agent_decision', 'play_small')
    lock_ready = _count(normalized, 'lock_ready', 'True') + _count(normalized, 'lock_ready', 'true')

    if rows == 0:
        status = 'empty'
        next_action = 'run_or_upload_data'
        blockers = ['no_rows']
    elif page_key == 'scanner_pro':
        blockers = _missing_columns(normalized, REQUIRED_FOR_SCANNER_HANDOFF)
        status = 'ready_for_pro_predictor' if scanner_coverage >= 0.80 else 'needs_better_scan'
        next_action = 'send_to_pro_predictor' if status == 'ready_for_pro_predictor' else 'rescan_with_more_books_or_sport_keys'
    elif page_key == 'pro_predictor':
        blockers = _missing_columns(normalized, REQUIRED_FOR_PREDICTOR_HANDOFF)
        status = 'ready_for_what_are_the_odds' if predictor_coverage >= 0.80 else 'needs_prediction_fields'
        next_action = 'send_to_what_are_the_odds' if status == 'ready_for_what_are_the_odds' else 'rerun_with_odds_and_event_times'
    elif page_key == 'what_are_the_odds':
        blockers = _missing_columns(normalized, REQUIRED_FOR_VALUE_HANDOFF)
        status = 'ready_for_lock_or_learning' if playable > 0 or value_coverage >= 0.80 else 'needs_value_review_fields'
        next_action = 'lock_future_plays_or_train_finished_results' if status == 'ready_for_lock_or_learning' else 'add_probabilities_prices_and_decisions'
    elif page_key == 'learning_memory':
        blockers = _missing_columns(normalized, REQUIRED_FOR_LEARNING_HANDOFF)
        status = 'ready_to_train' if resolved >= 5 else 'needs_finished_results'
        next_action = 'train_and_save_memory' if status == 'ready_to_train' else 'add_more_win_loss_results'
    else:
        blockers = []
        status = 'unknown_page'
        next_action = 'review_manually'

    score = 0.0
    if rows > 0:
        score += min(30.0, rows / 10.0)
        score += scanner_coverage * 15.0
        score += predictor_coverage * 20.0
        score += value_coverage * 20.0
        score += min(10.0, playable * 2.0)
        score += min(5.0, resolved)
    return {
        'page': page,
        'rows': rows,
        'status': status,
        'next_action': next_action,
        'handoff_score': round(max(0.0, min(100.0, score)), 2),
        'scanner_coverage': scanner_coverage,
        'predictor_coverage': predictor_coverage,
        'value_coverage': value_coverage,
        'learning_coverage': learning_coverage,
        'playable_rows': playable,
        'lock_ready_rows': lock_ready,
        'resolved_rows': resolved,
        'avg_agent_score': avg_agent_score,
        'avg_scanner_strength': avg_scanner_strength,
        'blockers': blockers,
    }


def page_health_frame(frame: pd.DataFrame | list[dict[str, Any]], *, page: str) -> pd.DataFrame:
    health = page_health(frame, page=page)
    flat = dict(health)
    flat['blockers'] = ' | '.join(health.get('blockers', []))
    return pd.DataFrame([flat])


def four_tool_recommendation(frame: pd.DataFrame | list[dict[str, Any]]) -> str:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return 'start_with_scanner_pro_or_upload_csv'
    if _resolved_count(normalized) >= 5:
        return 'learning_memory'
    if 'agent_decision' in normalized.columns and (_count(normalized, 'agent_decision', 'play_strong') + _count(normalized, 'agent_decision', 'play_small')) > 0:
        return 'what_are_the_odds_or_odds_lock'
    if 'model_probability' in normalized.columns and 'decimal_price' in normalized.columns:
        return 'what_are_the_odds'
    if 'decimal_price' in normalized.columns:
        return 'pro_predictor'
    return 'scanner_pro'

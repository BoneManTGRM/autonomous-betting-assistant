from __future__ import annotations

from typing import Any

import pandas as pd

from .prediction_snapshot import build_prediction_snapshots, snapshot_summary
from .proof_readiness import proof_readiness_summary
from .row_normalizer import normalize_frame
from .stat_validation import statistical_summary


def _has_value(frame: pd.DataFrame, column: str) -> bool:
    if frame is None or frame.empty or column not in frame.columns:
        return False
    return frame[column].fillna('').astype(str).str.strip().ne('').any()


def _count_values(frame: pd.DataFrame, column: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].fillna('').astype(str).str.strip().ne('').sum())


def intake_gate(frame: pd.DataFrame) -> dict[str, Any]:
    normalized = normalize_frame(frame)
    if normalized.empty:
        return {
            'rows': 0,
            'overall_status': 'blocked',
            'summary': 'No rows found.',
            'gates': [],
            'blockers': ['Upload or paste a non-empty CSV.'],
            'warnings': [],
            'next_actions': ['Upload a prediction/results CSV.'],
        }

    snapshots = build_prediction_snapshots(normalized, allow_auto_lock=False)
    lock_summary = snapshot_summary(snapshots)
    proof_summary = proof_readiness_summary(normalized)
    stats = statistical_summary(normalized)

    has_event = _has_value(normalized, 'event')
    has_prediction = _has_value(normalized, 'prediction')
    has_probability = _has_value(normalized, 'model_probability')
    has_odds = _has_value(normalized, 'decimal_price')
    has_timestamp = _has_value(normalized, 'prediction_timestamp') or _has_value(normalized, 'locked_at_utc')
    has_result = int(stats['wins'] + stats['losses']) > 0
    has_profit = _has_value(normalized, 'profit_units')
    has_closing = _has_value(normalized, 'closing_decimal_price')

    gates: list[dict[str, Any]] = []

    def add_gate(name: str, ready: bool, reason: str, required: str) -> None:
        gates.append({'gate': name, 'ready': bool(ready), 'status': 'ready' if ready else 'blocked', 'reason': reason, 'required': required})

    add_gate('CSV normalization', has_event or has_prediction or has_result, 'The file has recognizable prediction/result fields.' if (has_event or has_prediction or has_result) else 'The app could not detect basic prediction/result fields.', 'event/prediction/result aliases')
    add_gate('Learning memory', has_result and has_probability, 'Resolved results and probabilities are available.' if (has_result and has_probability) else 'Needs resolved win/loss rows plus model_probability. High-confidence fallback can be used only in Learning Memory.', 'result_status plus model_probability')
    add_gate('Statistical validation', has_result, 'Resolved wins/losses are available.' if has_result else 'Needs resolved win/loss rows.', 'result_status/win_loss/outcome')
    add_gate('Odds lock readiness', has_event and has_prediction and has_probability and has_odds, 'Rows have the required fields to be locked before events start.' if (has_event and has_prediction and has_probability and has_odds) else 'Needs event, prediction, model_probability, and decimal_price.', 'event, prediction, model_probability, decimal_price')
    add_gate('Official proof readiness', lock_summary['official_locked'] > 0, 'At least one row is already official locked.' if lock_summary['official_locked'] > 0 else 'No official locked rows detected. Use Odds Lock before events start.', 'official_locked snapshot rows')
    add_gate('ROI proof readiness', has_result and has_profit and has_odds, 'Results, odds, and profit_units are available.' if (has_result and has_profit and has_odds) else 'Needs results, odds, and profit_units.', 'result_status, decimal_price, profit_units')
    add_gate('CLV readiness', has_odds and has_closing, 'Locked odds and closing odds are available.' if (has_odds and has_closing) else 'Needs decimal_price and closing_decimal_price.', 'decimal_price plus closing_decimal_price')
    add_gate('Forward-test tracker', proof_summary['official_forward_proof'] > 0, 'Official forward-proof rows are available.' if proof_summary['official_forward_proof'] > 0 else 'No forward-proof rows yet.', 'official forward locked rows')

    blockers: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []

    if not has_event:
        blockers.append('Missing event/game/match column.')
    if not has_prediction:
        blockers.append('Missing prediction/pick/selection column.')
    if not has_probability:
        warnings.append('Missing model_probability. Learning and proof will be weaker.')
    if not has_odds:
        warnings.append('Missing decimal_price/best_price/odds. ROI and official proof will be limited.')
    if not has_timestamp:
        warnings.append('Missing prediction_timestamp/locked_at_utc. Historical rows should not be called forward proof.')
    if not has_result:
        warnings.append('No resolved win/loss rows detected yet.')
    if lock_summary['not_official'] > 0:
        warnings.append(f"{lock_summary['not_official']} rows are not official locked.")

    if not has_probability:
        next_actions.append('Add model_probability to future exports.')
    if not has_odds:
        next_actions.append('Add decimal_price and bookmaker/source to future exports.')
    if not has_timestamp:
        next_actions.append('Use Odds Lock before games start to create locked_at_utc and lock_hash.')
    if has_result and stats['total'] < 25:
        next_actions.append('Keep collecting resolved rows; current sample is below the 25-pick smoke-test target.')
    if has_odds and not has_closing:
        next_actions.append('Add closing_decimal_price later to measure CLV.')

    ready_count = sum(1 for gate in gates if gate['ready'])
    if blockers:
        overall = 'blocked'
    elif ready_count >= 5:
        overall = 'strong'
    elif ready_count >= 3:
        overall = 'usable'
    else:
        overall = 'limited'

    return {
        'rows': int(len(normalized)),
        'overall_status': overall,
        'summary': f'{ready_count} of {len(gates)} gates ready.',
        'recognized_counts': {
            'event': _count_values(normalized, 'event'),
            'prediction': _count_values(normalized, 'prediction'),
            'model_probability': _count_values(normalized, 'model_probability'),
            'decimal_price': _count_values(normalized, 'decimal_price'),
            'prediction_timestamp': _count_values(normalized, 'prediction_timestamp'),
            'result_status': _count_values(normalized, 'result_status'),
            'profit_units': _count_values(normalized, 'profit_units'),
            'closing_decimal_price': _count_values(normalized, 'closing_decimal_price'),
        },
        'gates': gates,
        'blockers': blockers,
        'warnings': warnings,
        'next_actions': next_actions,
        'lock_summary': lock_summary,
        'proof_summary': proof_summary,
        'statistical_summary': stats,
    }


def gates_frame(report: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(report.get('gates', []))


def recognized_counts_frame(report: dict[str, Any]) -> pd.DataFrame:
    counts = report.get('recognized_counts', {})
    return pd.DataFrame([{'field': key, 'recognized_rows': value} for key, value in counts.items()])

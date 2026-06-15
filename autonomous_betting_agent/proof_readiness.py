from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .audit import parse_float


def _safe(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value).strip()


def _first(row: Mapping[str, Any], *names: str) -> str:
    normalized = {str(key).lower().replace(' ', '_').replace('-', '_'): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower().replace(' ', '_').replace('-', '_'))
        if _safe(value):
            return _safe(value)
    return ''


def classify_evidence_row(row: Mapping[str, Any]) -> tuple[str, str]:
    lock_status = _first(row, 'lock_status').lower()
    probability_source = _first(row, 'probability_source').lower()
    decimal_price = parse_float(_first(row, 'decimal_price', 'best_price', 'odds'))
    probability = parse_float(_first(row, 'model_probability', 'probability', 'final_probability', 'final_probability_value'))
    result = _first(row, 'result_status', 'outcome', 'result', 'win_loss').lower()
    timestamp = _first(row, 'locked_at_utc', 'prediction_timestamp', 'odds_timestamp')
    source = _first(row, 'source', 'source_file').lower()

    has_result = result in {'win', 'won', 'loss', 'lost', '0', '1'}
    has_probability = probability is not None
    has_odds = decimal_price is not None and decimal_price > 1.0
    has_timestamp = bool(timestamp)

    if lock_status == 'official_locked' and has_probability and has_odds and has_timestamp:
        return 'official_forward_proof', 'Official locked pick with probability, odds, timestamp, and hashable snapshot.'
    if has_result and has_probability and has_odds:
        return 'historical_roi_candidate', 'Historical graded row has odds and probability, but may not be forward-locked.'
    if has_result and has_probability and (probability_source.startswith('fallback_') or 'high confidence' in source):
        return 'learning_only_backfill', 'Historical result useful for learning, but probability was inferred/fallback and odds are missing.'
    if has_result:
        return 'historical_result_only', 'Historical result exists, but odds/probability proof is incomplete.'
    return 'unresolved_or_unusable', 'Row is unresolved or missing proof fields.'


def build_proof_readiness_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=['evidence_level', 'evidence_reason'])
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient='records'):
        level, reason = classify_evidence_row(raw)
        item = dict(raw)
        item['evidence_level'] = level
        item['evidence_reason'] = reason
        rows.append(item)
    return pd.DataFrame(rows)


def proof_readiness_summary(frame: pd.DataFrame) -> dict[str, Any]:
    proof = build_proof_readiness_frame(frame)
    if proof.empty:
        return {
            'rows': 0,
            'proof_score': 0,
            'official_forward_proof': 0,
            'historical_roi_candidate': 0,
            'learning_only_backfill': 0,
            'historical_result_only': 0,
            'unresolved_or_unusable': 0,
            'safe_claim': 'No proof data loaded yet.',
            'unsafe_claim': 'Do not claim accuracy or profitability yet.',
        }
    counts = proof['evidence_level'].value_counts().to_dict()
    rows = int(len(proof))
    official = int(counts.get('official_forward_proof', 0))
    roi_candidate = int(counts.get('historical_roi_candidate', 0))
    learning = int(counts.get('learning_only_backfill', 0))
    result_only = int(counts.get('historical_result_only', 0))
    unresolved = int(counts.get('unresolved_or_unusable', 0))
    score = min(100, int(round((official * 100 + roi_candidate * 55 + learning * 25 + result_only * 15) / max(rows, 1))))
    if official >= 100:
        safe_claim = f'{official} forward-locked picks are available for official proof review.'
    elif official > 0:
        safe_claim = f'{official} forward-locked picks exist, but sample size is still early.'
    elif learning > 0:
        safe_claim = f'{learning} historical learning rows exist. They support early pattern research, not official ROI proof.'
    elif roi_candidate > 0:
        safe_claim = f'{roi_candidate} historical ROI candidate rows exist, but forward lock status must be checked.'
    else:
        safe_claim = 'Only incomplete or unresolved evidence exists.'
    unsafe_claim = 'Do not claim proven profitability unless picks have timestamped odds, model probability, and clean results from a forward test.'
    return {
        'rows': rows,
        'proof_score': score,
        'official_forward_proof': official,
        'historical_roi_candidate': roi_candidate,
        'learning_only_backfill': learning,
        'historical_result_only': result_only,
        'unresolved_or_unusable': unresolved,
        'safe_claim': safe_claim,
        'unsafe_claim': unsafe_claim,
    }


def safe_claims_for_current_state(summary: Mapping[str, Any]) -> list[str]:
    rows = int(summary.get('rows') or 0)
    official = int(summary.get('official_forward_proof') or 0)
    learning = int(summary.get('learning_only_backfill') or 0)
    claims = []
    if learning:
        claims.append(f'Historical learning set currently contains {learning} usable backfilled rows.')
    if official:
        claims.append(f'There are {official} official forward-locked proof rows.')
    if rows:
        claims.append('The system now separates learning evidence from official proof evidence.')
    claims.append('The strongest next proof step is a forward test where every pick is locked before game start with odds and model probability.')
    return claims

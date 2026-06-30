from __future__ import annotations

import hashlib
from typing import Any, Mapping

import pandas as pd

from .audit import parse_float

ALIASES = {
    'event': ('event', 'event_name', 'game', 'match', 'fixture', 'partido'),
    'sport': ('sport', 'sport_title', 'sport_key', 'league', 'competition', 'deporte'),
    'market_type': ('market_type', 'market', 'bet_type', 'prop_type', 'tipo_mercado'),
    'prediction': ('prediction', 'pick', 'selection', 'predicted_side', 'predicted_winner', 'favorite', 'prediccion', 'pronostico'),
    'model_probability': ('model_probability', 'final_probability', 'final_probability_value', 'calibrated_probability', 'probability', 'pick_probability', 'confidence_probability', 'model_probability_clean', 'probabilidad', 'prob_final'),
    'decimal_price': ('decimal_price', 'best_price', 'decimal_odds', 'odds_decimal', 'odds', 'price', 'sportsbook_odds', 'average_price', 'avg_price', 'cuota', 'mejor_cuota'),
    'american_odds': ('american_odds', 'american_price', 'moneyline'),
    'bookmaker': ('bookmaker', 'best_bookmaker', 'sportsbook', 'book'),
    'odds_source': ('odds_source', 'source', 'source_file'),
    'prediction_timestamp': ('prediction_timestamp', 'locked_at_utc', 'odds_timestamp', 'created_at', 'scan_timestamp'),
    'event_start_utc': ('event_start_utc', 'known_start_utc', 'start', 'commence_time', 'game_start', 'match_start', 'scheduled_start'),
    'odds_timestamp': ('odds_timestamp', 'price_timestamp', 'last_odds_update', 'last_update'),
    'result_status': (
        'verified_grade', 'verified_result', 'verified_status', 'verified_outcome', 'verified_result_status',
        'grade', 'final_grade', 'proof_grade', 'pick_grade', 'row_grade', 'result_grade', 'manual_grade',
        'result_status', 'outcome', 'result', 'win_loss', 'graded_result', 'status', 'resultado',
    ),
    'winner': ('winner', 'actual_winner', 'winning_side', 'final_winner', 'ganador'),
    'final_score': ('verified_final_result', 'final_score', 'score', 'actual_score', 'result_note'),
    'stake_units': ('stake_units', 'recommended_stake_units', 'suggested_stake_units', 'stake'),
    'recommended_stake_units': ('recommended_stake_units', 'suggested_stake_units'),
    'profit_units': ('profit_units', 'units'),
    'decision': ('decision', 'agent_decision'),
    'confidence_tier': ('confidence_tier', 'confidence', 'confidence_bucket', 'public_confidence'),
    'volume_tier': ('volume_tier', 'tier', 'ultra80_tier'),
    'ultra80_candidate': ('ultra80_candidate', 'strict_ultra80_candidate'),
    'api_coverage_score': ('api_coverage_score', 'api_coverage'),
    'books': ('books', 'bookmaker_count', 'source_count', 'bookmakers'),
    'agent_score': ('agent_score', 'decision_score'),
    'scanner_strength_score': ('scanner_strength_score', 'scanner_score'),
    'model_edge': ('model_edge', 'model_market_edge', 'edge_probability', 'edge'),
    'computed_ev_decimal': ('computed_ev_decimal', 'estimated_ev_decimal', 'estimated_ev_value', 'estimated_ev', 'expected_value_per_unit', 'ev', 'profit_expected_value'),
    'closing_decimal_price': ('closing_decimal_price', 'closing_price', 'close_decimal', 'closing_odds'),
    '_robust_decimal_price': ('_robust_decimal_price', 'robust_decimal_price', 'worst_price'),
    '_robust_expected_value': ('_robust_expected_value', 'robust_expected_value'),
    '_robust_profit_at_80_percent': ('_robust_profit_at_80_percent', 'robust_profit_at_80_percent'),
    '_price_range_risk': ('_price_range_risk', 'price_range_risk', 'price_range'),
}

VOID_LABELS = {
    'void', 'push', 'pushed', 'draw_no_bet_push', 'cancelled', 'canceled',
    'cancelation', 'cancellation', 'postponed', 'abandoned', 'no_action',
}

RESULT_MAP = {
    'won': 'win', 'winner': 'win', 'winning': 'win', 'win': 'win', 'w': 'win', 'correct': 'win', 'hit': 'win', 'true': 'win', 'yes': 'win', '1': 'win', '1.0': 'win',
    'ganada': 'win', 'gano': 'win', 'ganó': 'win', 'victoria': 'win', 'acierto': 'win',
    'lost': 'loss', 'loser': 'loss', 'losing': 'loss', 'loss': 'loss', 'l': 'loss', 'incorrect': 'loss', 'miss': 'loss', 'false': 'loss', 'no': 'loss', '0': 'loss', '0.0': 'loss',
    'perdida': 'loss', 'perdio': 'loss', 'perdió': 'loss', 'derrota': 'loss', 'fallo': 'loss',
    **{label: 'void' for label in VOID_LABELS},
    'pending': 'pending', 'ungraded': 'pending', 'not_graded': 'pending', 'not graded': 'pending', 'unknown': 'pending', 'scheduled': 'pending', 'live': 'pending', 'unverified_or_pending': 'pending',
}

RESOLVED_RESULT_STATUSES = {'win', 'loss', 'void'}
PENDING_RESULT_STATUSES = {'pending', 'unknown', 'scheduled', 'live', '', 'needs_review'}

DEDUPLICATION_COLUMNS = [
    'proof_id',
    'event_id',
    'event',
    'event_start_utc',
    'sport',
    'market_type',
    'line_point',
    'prediction',
    'bookmaker',
    'decimal_price',
]

TRUTHY_VALUES = {'true', '1', 'yes', 'y', 'pass', 'ok'}


def clean_key(value: Any) -> str:
    return str(value or '').strip().lower().replace(' ', '_').replace('-', '_')


def safe_text(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {'nan', 'none', 'null', 'n/a', 'na'}:
        return ''
    return text


def normalized_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
    return {clean_key(key): value for key, value in row.items()}


def first_value(row: Mapping[str, Any], aliases: tuple[str, ...]) -> Any:
    normalized = normalized_mapping(row)
    for alias in aliases:
        value = normalized.get(clean_key(alias))
        if safe_text(value):
            return value
    return ''


def first_text(row: Mapping[str, Any], canonical_name: str) -> str:
    return safe_text(first_value(row, ALIASES.get(canonical_name, (canonical_name,))))


def numeric_value(row: Mapping[str, Any], canonical_name: str) -> float | None:
    return parse_float(first_value(row, ALIASES.get(canonical_name, (canonical_name,))))


def probability_value(row: Mapping[str, Any], canonical_name: str = 'model_probability') -> float | None:
    value = numeric_value(row, canonical_name)
    if value is None:
        return None
    if 1.0 < value <= 100.0:
        value /= 100.0
    if 0.0 < value < 1.0:
        return value
    return None


def _mapped_status_values(row: Mapping[str, Any]) -> list[str]:
    normalized = normalized_mapping(row)
    statuses: list[str] = []
    for alias in ALIASES['result_status']:
        raw = safe_text(normalized.get(clean_key(alias))).lower()
        if not raw:
            continue
        statuses.append(RESULT_MAP.get(raw, raw))
    return statuses


def has_void_label(row: Mapping[str, Any]) -> bool:
    normalized = normalized_mapping(row)
    aliases = ALIASES['result_status'] + ALIASES['final_score']
    for alias in aliases:
        value = safe_text(normalized.get(clean_key(alias))).lower()
        if not value:
            continue
        mapped = RESULT_MAP.get(value, value)
        if mapped == 'void' or value in VOID_LABELS:
            return True
        if any(label in value for label in VOID_LABELS):
            return True
    return False


def result_status(row: Mapping[str, Any]) -> str:
    statuses = _mapped_status_values(row)
    # A void/push/cancellation label is a terminal settlement state and must not
    # be counted as a loss even when another legacy field still says loss.
    if has_void_label(row):
        return 'void'
    # API/result sync can set result_status=win/loss while older upload fields
    # like verified_grade remain pending. Never let a pending alias overwrite a
    # later resolved grade.
    for status in statuses:
        if status in {'win', 'loss'}:
            return status
    for status in statuses:
        if status and status not in PENDING_RESULT_STATUSES:
            return status
    pick = first_text(row, 'prediction').lower()
    winner = first_text(row, 'winner').lower()
    if pick and winner:
        return 'win' if pick == winner else 'loss'
    return 'pending'


def normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = {name: first_text(row, name) for name in ALIASES}
    prob = probability_value(row, 'model_probability')
    if prob is not None:
        out['model_probability'] = round(prob, 6)
    for field in (
        'decimal_price', 'api_coverage_score', 'books', 'agent_score', 'scanner_strength_score',
        'model_edge', 'computed_ev_decimal', 'closing_decimal_price', '_robust_decimal_price',
        '_robust_expected_value', '_robust_profit_at_80_percent', '_price_range_risk',
        'recommended_stake_units', 'stake_units',
    ):
        value = numeric_value(row, field)
        if value is not None:
            if field == 'api_coverage_score' and value > 1.0:
                value /= 100.0
            out[field] = round(value, 6)
    out['result_status'] = result_status(row)
    return out


def _truthy(value: Any) -> bool:
    return safe_text(value).lower() in TRUTHY_VALUES


def _needs_synthetic_proof(row: Mapping[str, Any]) -> bool:
    if safe_text(row.get('proof_id')) and safe_text(row.get('locked_at_utc')):
        return False
    status = result_status(row)
    return _truthy(row.get('lock_ready')) or status in {'win', 'loss', 'void', 'pending'}


def _synthetic_proof_id(row: Mapping[str, Any]) -> str:
    key = '|'.join([
        safe_text(row.get('event_id')),
        safe_text(row.get('event')),
        safe_text(row.get('event_start_utc')),
        safe_text(row.get('sport')),
        safe_text(row.get('market_type')),
        safe_text(row.get('line_point')),
        safe_text(row.get('prediction')),
        safe_text(row.get('decimal_price')),
    ])
    return 'OLP-SYN-' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:12].upper()


def _add_synthetic_proof_fields(item: dict[str, Any]) -> None:
    if not _needs_synthetic_proof(item):
        return
    if not safe_text(item.get('proof_id')):
        item['proof_id'] = _synthetic_proof_id(item)
    if not safe_text(item.get('locked_at_utc')):
        item['locked_at_utc'] = safe_text(item.get('prediction_timestamp') or item.get('odds_timestamp') or item.get('verified_updated_utc') or item.get('created_at'))
    if not safe_text(item.get('proof_source_type')):
        item['proof_source_type'] = 'lock_ready_verified_tracker'
    if not safe_text(item.get('proof_status')):
        item['proof_status'] = 'locked_before_start'


def _dedupe_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    proof_id = safe_text(row.get('proof_id'))
    if proof_id:
        return ('proof_id', proof_id)
    event_id = safe_text(row.get('event_id'))
    if event_id:
        return (
            'event_id',
            event_id,
            safe_text(row.get('market_type')).lower(),
            safe_text(row.get('line_point')).lower(),
            safe_text(row.get('prediction')).lower(),
        )
    return tuple(safe_text(row.get(column)).lower() for column in DEDUPLICATION_COLUMNS if column != 'proof_id')


def dedupe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    seen: set[tuple[str, ...]] = set()
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient='records'):
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(row))
    return pd.DataFrame(rows)


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows = []
    for raw in frame.to_dict(orient='records'):
        item = dict(raw)
        normalized = normalize_row(raw)
        for key, value in normalized.items():
            if key not in item or not safe_text(item.get(key)):
                item[key] = value
        item['result_status'] = normalized['result_status']
        _add_synthetic_proof_fields(item)
        rows.append(item)
    return dedupe_frame(pd.DataFrame(rows))

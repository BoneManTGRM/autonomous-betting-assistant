"""Session-only paper evidence capture; not a forecast or proof generator."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from numbers import Integral
import numpy as np
from typing import Any

from .prospective_evidence import PREDICTION_FIELDS, PROTOCOL_FIELDS, MAX_ROWS, _check_prediction

# Explicit safe prediction fields only. Do not export provider keys, arbitrary
# API error payloads, private context, or outcome fields from a mixed session.
CAPTURE_FIELDS = PREDICTION_FIELDS | {
    'event', 'sport_key', 'event_start_utc', 'event_date', 'home_team', 'away_team',
    'line_point', 'prediction', 'model_probability', 'model_probability_clean',
    'learned_model_probability', 'market_probability', 'raw_market_probability',
    'market_implied_probability', 'decimal_price', 'odds_at_pick', 'best_price',
    'average_price', 'worst_price', 'bookmaker', 'bookmaker_count', 'books',
    'market_overround', 'prediction_timestamp', 'model_probability_source',
    'configured_api_sources', 'api_sources_used', 'agent_decision', 'agent_score',
    'scanner_strength_score', 'pattern_points', 'learning_adjustment_score',
}
ALIASES = {'event_start': 'event_start_utc', 'event_label': 'event',
           'selection_label': 'prediction', 'decimal_odds': 'decimal_price'}
MAX_BYTES = 8_000_000


def _scalar(value: Any) -> Any:
    if value is None or type(value) in (str, bool, int):
        if isinstance(value, str) and len(value) > 10_000:
            raise ValueError('Oversized text in a prediction field')
        return value
    if isinstance(value, Integral):
        return int(value)
    if type(value) in (float, np.float16, np.float32, np.float64):
        number = float(value)
        if not math.isfinite(number):
            return {'nonfinite_number': 'NaN' if math.isnan(number) else ('+Infinity' if number > 0 else '-Infinity')}
        return number
    # No str/repr fallback: it can execute custom code or hide lost meaning.
    raise ValueError('Unsupported value type in a prediction field')


def capture_predictions(rows: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Capture selected safe fields for every current passed row, without mutation.

    There is deliberately no ledger fallback, new scan, schema backfill or
    packet issuance. The source may already be filtered, stale or rewritten by
    legacy inference; the local capture clock does not establish prediction time.
    """
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS or any(not isinstance(r, dict) for r in rows):
        raise ValueError(f'Supply 1–{MAX_ROWS} current session row objects')
    clock = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError('Timezone-aware capture clock required')
    clock = clock.astimezone(timezone.utc)
    captured = []
    for index, source in enumerate(rows):
        if any(not isinstance(k, str) for k in source):
            raise ValueError('Prediction field names must be strings')
        fields = {key: _scalar(value) for key, value in source.items() if key in CAPTURE_FIELDS}
        missing = sorted(key for key in PREDICTION_FIELDS if key not in fields or fields[key] is None or fields[key] == '')
        # Conservative: alias fields remain visible as supplied, but are not
        # silently promoted to the stricter packet schema or counted as proof.
        hints = {key: alias for key, alias in ALIASES.items() if key in missing and alias in fields}
        validation_error = None
        if not missing:
            try:
                _check_prediction({key: fields[key] for key in PREDICTION_FIELDS}, clock)
            except (ValueError, TypeError, OverflowError) as exc:
                validation_error = str(exc)
        captured.append({'source_row_index': index, 'captured_fields': fields,
                         'omitted_field_names': sorted(set(source) - CAPTURE_FIELDS),
                         'missing_fields': missing, 'possible_aliases_not_applied': hints,
                         'structural_error': validation_error,
                         'exact_prediction_fields_valid': not missing and validation_error is None})
    body = {'schema': 'aba-session-prediction-capture-v1', 'captured_at': clock.isoformat(),
            'source_session_key': 'pro_predictor_all_rows',
            'source_scope': 'current_session_passed_rows_only_not_all_scanned_candidates',
            'capture_time_is_prediction_time': False,
            'snapshot_scope': 'allowlisted_prediction_fields_not_full_original_records',
            'row_count': len(rows), 'rows': captured,
            'rows_with_missing_or_invalid_fields': sum(not r['exact_prediction_fields_valid'] for r in captured),
            'required_protocol_fields': sorted(PROTOCOL_FIELDS),
            'packet_ready': False, 'protocol_declared': False, 'cohort_consistency_reviewed': False,
            'independently_verified': False, 'authenticated_pre_event_commitment': False,
            'training_allowed': False, 'promotion_allowed': False, 'live_mutation_allowed': False,
            'predictive_gain_proven': False, 'paper_only': True}
    serialized = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(serialized.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Prediction snapshot exceeds size limit; no partial cohort was exported')
    return {**body, 'capture_sha256': hashlib.sha256(serialized.encode('utf-8')).hexdigest()}

"""Session-only pre-ranking observation. Never a raw-model or timing attestation."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
import numpy as np

from .prediction_capture import _scalar

SESSION_KEY = 'aba_pre_ranking_evidence_json'
MAX_ROWS = 1000
MAX_BYTES = 8_000_000
SCALAR_TYPES = {type(None), str, bool, int, float, np.int8, np.int16, np.int32,
                np.int64, np.uint8, np.uint16, np.uint32, np.uint64,
                np.float16, np.float32, np.float64}
FIELDS = {
    'event_id': 'provider_event_id', 'event': 'event_label',
    'sport': 'sport', 'sport_key': 'sport_key',
    'event_start_utc': 'event_start_as_supplied',
    'market_type': 'market_type_as_supplied', 'line_point': 'line_point_as_supplied',
    'prediction': 'selection_label',
    'model_probability': 'stage_model_probability',
    'model_probability_clean': 'stage_model_probability_clean',
    'market_probability': 'stage_market_probability',
    'learned_model_probability': 'stage_learned_probability_if_present',
    'decimal_price': 'decimal_price', 'best_price': 'best_price',
    'average_price': 'average_price', 'worst_price': 'worst_price',
    'bookmaker': 'bookmaker_display_title', 'bookmaker_count': 'bookmaker_count',
}


def capture_stage_evidence(rows: Any, *, origin_route: str, now: datetime | None = None) -> str:
    """Return detached immutable JSON, without modifying any pipeline records.

    All built rows are retained or the whole snapshot fails. This boundary is
    AFTER provider summarization, optional calibration and build-time filtering.
    No missing upstream field is backfilled or promoted to a stricter schema.
    """
    if origin_route not in {'pro_predictor', 'pro_predictor_volume'}:
        raise ValueError('Unknown prediction route')
    if type(rows) is not list or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError('Supply 1–1000 built rows')
    clock = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError('Aware stage capture clock required')
    captured = []
    for index, row in enumerate(rows):
        if type(row) is not dict or any(type(key) is not str for key in row):
            raise ValueError('Built rows must be objects with string keys')
        # Reject subclasses before conversion: even int/str subclasses may run
        # arbitrary __int__/__len__ hooks. Do not change legacy capture behavior.
        if any(type(row[source]) not in SCALAR_TYPES for source in FIELDS if source in row):
            raise ValueError('Unsupported stage field scalar type')
        fields = {target: _scalar(row[source]) for source, target in FIELDS.items() if source in row}
        captured.append({'built_row_index': index, 'fields': fields,
                         'missing_stage_fields': sorted(set(FIELDS.values()) - set(fields)),
                         'omitted_field_count': len(set(row) - set(FIELDS))})
    body = {
        'schema': 'aba-pre-ranking-stage-evidence-v1',
        'origin_route': origin_route,
        'stage_captured_at': clock.astimezone(timezone.utc).isoformat(),
        'scope': 'all_built_rows_before_ranking_after_provider_and_build_filters',
        'probability_semantics': 'stage_values_may_already_include_market_calibration_not_independent_raw_forecasts',
        'row_count': len(captured), 'rows': captured,
        'unknown_provenance': ['original_prediction_time', 'odds_observation_time',
            'immutable_model_artifact', 'frozen_baseline_artifact_and_probability',
            'canonical_settlement_identity', 'authenticated_pre_event_commitment'],
        'capture_time_is_prediction_time': False,
        'complete_scanned_population': False, 'packet_ready': False,
        'independently_verified': False, 'training_allowed': False,
        'promotion_allowed': False, 'predictive_gain_proven': False,
        'paper_only': True,
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    result = json.dumps({**body, 'content_sha256': digest}, ensure_ascii=False,
                        sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(result.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Stage snapshot exceeds size limit; no partial export')
    return result

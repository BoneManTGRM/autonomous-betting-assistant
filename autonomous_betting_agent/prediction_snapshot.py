from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from .audit import enrich_prediction_frame, parse_float
from .local_users import DEFAULT_USER_ID, sanitize_user_id

SNAPSHOT_SCHEMA_VERSION = 'prediction-snapshot-v1'
REQUIRED_OFFICIAL_FIELDS = ('event', 'prediction', 'model_probability', 'decimal_price')


@dataclass(frozen=True)
class SnapshotVerification:
    valid: bool
    rows_checked: int
    first_bad_row: int | None
    message: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


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


def _probability(row: Mapping[str, Any]) -> str:
    return _first(row, 'model_probability', 'final_probability', 'final_probability_value', 'probability')


def _canonical_payload(row: Mapping[str, Any]) -> str:
    payload = {str(key): _safe(value) for key, value in row.items() if str(key) != 'lock_hash'}
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def lock_hash(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload(row).encode('utf-8')).hexdigest()


def snapshot_id(row: Mapping[str, Any]) -> str:
    basis = '|'.join([
        _safe(row.get('local_user_id')),
        _safe(row.get('locked_at_utc')),
        _safe(row.get('event')),
        _safe(row.get('market_type')),
        _safe(row.get('prediction')),
        _safe(row.get('decimal_price')),
    ])
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()[:24]


def official_lock_status(row: Mapping[str, Any]) -> tuple[str, str]:
    missing: list[str] = []
    if not _safe(row.get('event')):
        missing.append('event')
    if not _safe(row.get('prediction')):
        missing.append('prediction')
    if parse_float(row.get('model_probability')) is None:
        missing.append('model_probability')
    if parse_float(row.get('decimal_price')) is None:
        missing.append('decimal_price')
    if not _safe(row.get('locked_at_utc')):
        missing.append('locked_at_utc')
    if missing:
        return 'not_official', 'Missing required fields: ' + ', '.join(missing)
    return 'official_locked', 'Official prediction snapshot locked before grading.'


def build_prediction_snapshots(frame: pd.DataFrame, *, user_id: str = DEFAULT_USER_ID, locked_at_utc: str | None = None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    clean_user = sanitize_user_id(user_id)
    enriched = enrich_prediction_frame(frame)
    locked_at = locked_at_utc or utc_now_iso()
    rows: list[dict[str, Any]] = []
    for raw in enriched.to_dict(orient='records'):
        row = {
            'snapshot_schema_version': SNAPSHOT_SCHEMA_VERSION,
            'local_user_id': clean_user,
            'snapshot_id': '',
            'locked_at_utc': _first(raw, 'prediction_timestamp', 'locked_at_utc', 'odds_timestamp') or locked_at,
            'event': _first(raw, 'event', 'game', 'match'),
            'sport': _first(raw, 'sport', 'league'),
            'market_type': _first(raw, 'market_type', 'market', 'bet_type'),
            'prediction': _first(raw, 'prediction', 'pick', 'selection'),
            'model_probability': _probability(raw),
            'decimal_price': _first(raw, 'decimal_price', 'best_price', 'odds'),
            'american_odds': _first(raw, 'american_odds', 'american_price'),
            'implied_probability': _first(raw, 'implied_probability', 'break_even_win_rate'),
            'estimated_ev_decimal': _first(raw, 'estimated_ev_decimal', 'computed_ev_decimal', 'estimated_ev_value'),
            'bookmaker': _first(raw, 'bookmaker', 'best_bookmaker', 'sportsbook'),
            'odds_source': _first(raw, 'odds_source', 'source'),
            'data_sources_used': _first(raw, 'data_sources_used', 'api_sources', 'source_file'),
            'decision': _first(raw, 'decision'),
            'confidence_tier': _first(raw, 'confidence_tier'),
            'lock_status': '',
            'lock_reason': '',
            'lock_hash': '',
        }
        row['snapshot_id'] = snapshot_id(row)
        row['lock_status'], row['lock_reason'] = official_lock_status(row)
        row['lock_hash'] = lock_hash(row)
        rows.append(row)
    return pd.DataFrame(rows)


def verify_snapshots(frame: pd.DataFrame) -> SnapshotVerification:
    if frame is None or frame.empty:
        return SnapshotVerification(True, 0, None, 'No snapshots to verify.')
    for idx, row in enumerate(frame.to_dict(orient='records')):
        expected = lock_hash(row)
        actual = _safe(row.get('lock_hash'))
        if expected != actual:
            return SnapshotVerification(False, idx + 1, idx, 'Snapshot lock hash does not match row contents.')
    return SnapshotVerification(True, len(frame), None, 'All snapshot hashes are valid.')


def snapshot_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {'total': 0, 'official_locked': 0, 'not_official': 0, 'missing_odds': 0, 'missing_probability': 0}
    status = frame.get('lock_status', pd.Series(dtype=str)).fillna('').astype(str)
    reason = frame.get('lock_reason', pd.Series(dtype=str)).fillna('').astype(str).str.lower()
    return {
        'total': int(len(frame)),
        'official_locked': int(status.eq('official_locked').sum()),
        'not_official': int(status.ne('official_locked').sum()),
        'missing_odds': int(reason.str.contains('decimal_price', na=False).sum()),
        'missing_probability': int(reason.str.contains('model_probability', na=False).sum()),
    }

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from .audit import enrich_prediction_frame
from .local_users import DEFAULT_USER_ID, ensure_user_dirs, sanitize_user_id, user_dir
from .security import escape_csv_formula_value, redact_secret_text

LEDGER_SCHEMA_VERSION = 'proof-ledger-v1'
LEDGER_COLUMNS = [
    'ledger_schema_version',
    'local_user_id',
    'prediction_id',
    'prediction_timestamp',
    'event',
    'sport',
    'market_type',
    'prediction',
    'model_probability',
    'decimal_price',
    'american_odds',
    'implied_probability',
    'bookmaker',
    'odds_source',
    'decision',
    'decision_reason',
    'confidence_tier',
    'result_status',
    'clean_grading_status',
    'audit_inclusion',
    'stake_units',
    'profit_units',
    'roi_percent',
    'previous_hash',
    'row_hash',
]

HASH_EXCLUDE_COLUMNS = {'row_hash'}


@dataclass(frozen=True)
class LedgerVerification:
    valid: bool
    rows_checked: int
    first_bad_row: int | None
    message: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def ledger_path(user_id: str = DEFAULT_USER_ID) -> Path:
    clean_id = sanitize_user_id(user_id)
    ensure_user_dirs(clean_id)
    return user_dir(clean_id) / 'ledgers' / 'prediction_ledger.csv'


def _safe_text(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    text = str(value)
    text = str(redact_secret_text(text))
    text = str(escape_csv_formula_value(text))
    return text


def _canonical_payload(row: Mapping[str, Any]) -> str:
    payload = {str(key): _safe_text(value) for key, value in row.items() if str(key) not in HASH_EXCLUDE_COLUMNS}
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_row_hash(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload(row).encode('utf-8')).hexdigest()


def prediction_id_for_row(row: Mapping[str, Any]) -> str:
    # The ledger row hash still includes the timestamp for tamper evidence, but
    # duplicate detection must stay stable when the same prediction is uploaded
    # again without an original source timestamp. Therefore the prediction_id is
    # based on the actual pick identity, not the append time.
    basis = '|'.join([
        _safe_text(row.get('local_user_id')),
        _safe_text(row.get('event')),
        _safe_text(row.get('market_type')),
        _safe_text(row.get('prediction')),
        _safe_text(row.get('decimal_price')),
    ])
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()[:24]


def _first(row: Mapping[str, Any], names: Iterable[str]) -> Any:
    lowered = {str(key).lower().replace(' ', '_').replace('-', '_'): value for key, value in row.items()}
    for name in names:
        value = lowered.get(str(name).lower().replace(' ', '_').replace('-', '_'))
        if value not in (None, ''):
            return _safe_text(value)
    return ''


def _model_probability(row: Mapping[str, Any]) -> Any:
    return _first(row, ('model_probability', 'final_probability_value', 'final_probability', 'probability'))


def load_ledger(user_id: str = DEFAULT_USER_ID) -> pd.DataFrame:
    path = ledger_path(user_id)
    if not path.exists():
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    try:
        # The proof ledger is small and local. Use the Python CSV engine to avoid
        # intermittent pandas C-parser crashes seen in GitHub Actions smoke tests.
        frame = pd.read_csv(path, engine='python')
    except Exception:
        return pd.DataFrame(columns=LEDGER_COLUMNS)
    for column in LEDGER_COLUMNS:
        if column not in frame.columns:
            frame[column] = ''
    return frame[LEDGER_COLUMNS + [col for col in frame.columns if col not in LEDGER_COLUMNS]]


def last_hash(user_id: str = DEFAULT_USER_ID) -> str:
    frame = load_ledger(user_id)
    if frame.empty or 'row_hash' not in frame.columns:
        return 'GENESIS'
    values = frame['row_hash'].dropna().astype(str).str.strip()
    return values.iloc[-1] if not values.empty else 'GENESIS'


def build_ledger_rows(predictions: pd.DataFrame, *, user_id: str = DEFAULT_USER_ID, display_name: str = '', previous_hash: str | None = None) -> pd.DataFrame:
    clean_user_id = sanitize_user_id(user_id)
    enriched = enrich_prediction_frame(predictions) if predictions is not None and not predictions.empty else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    prev = previous_hash or last_hash(clean_user_id)
    for raw in enriched.to_dict(orient='records'):
        timestamp = _safe_text(_first(raw, ('prediction_timestamp', 'odds_timestamp', 'created_at', 'scan_timestamp'))) or utc_now_iso()
        row = {
            'ledger_schema_version': LEDGER_SCHEMA_VERSION,
            'local_user_id': clean_user_id,
            'prediction_id': '',
            'prediction_timestamp': timestamp,
            'event': _first(raw, ('event', 'game', 'match')),
            'sport': _first(raw, ('sport', 'league')),
            'market_type': _first(raw, ('market_type', 'market', 'bet_type')),
            'prediction': _first(raw, ('prediction', 'pick', 'selection')),
            'model_probability': _model_probability(raw),
            'decimal_price': _first(raw, ('decimal_price', 'best_price', 'odds')),
            'american_odds': _first(raw, ('american_odds', 'american_price')),
            'implied_probability': _first(raw, ('implied_probability', 'break_even_win_rate')),
            'bookmaker': _first(raw, ('bookmaker', 'best_bookmaker', 'sportsbook')),
            'odds_source': _first(raw, ('odds_source', 'source')),
            'decision': _first(raw, ('decision',)),
            'decision_reason': _first(raw, ('decision_reason', 'reason')),
            'confidence_tier': _first(raw, ('confidence_tier',)),
            'result_status': _first(raw, ('result_status',)),
            'clean_grading_status': _first(raw, ('clean_grading_status',)),
            'audit_inclusion': _first(raw, ('audit_inclusion',)),
            'stake_units': _first(raw, ('stake_units', 'stake')),
            'profit_units': _first(raw, ('profit_units',)),
            'roi_percent': _first(raw, ('roi_percent',)),
            'previous_hash': _safe_text(prev),
            'row_hash': '',
        }
        row['prediction_id'] = prediction_id_for_row(row)
        row['row_hash'] = compute_row_hash(row)
        prev = row['row_hash']
        rows.append(row)
    return pd.DataFrame(rows, columns=LEDGER_COLUMNS)


def append_predictions_to_ledger(predictions: pd.DataFrame, *, user_id: str = DEFAULT_USER_ID, display_name: str = '', dedupe: bool = True) -> pd.DataFrame:
    clean_user_id = sanitize_user_id(user_id)
    existing = load_ledger(clean_user_id)
    new_rows = build_ledger_rows(predictions, user_id=clean_user_id, display_name=display_name, previous_hash=last_hash(clean_user_id))
    if dedupe and not existing.empty and not new_rows.empty:
        seen = set(existing['prediction_id'].fillna('').astype(str)) if 'prediction_id' in existing.columns else set()
        new_rows = new_rows[~new_rows['prediction_id'].astype(str).isin(seen)].copy()
    combined = pd.concat([existing, new_rows], ignore_index=True, sort=False) if not existing.empty else new_rows
    path = ledger_path(clean_user_id)
    path.write_text(combined.to_csv(index=False), encoding='utf-8')
    return combined


def verify_hash_chain(frame: pd.DataFrame) -> LedgerVerification:
    if frame is None or frame.empty:
        return LedgerVerification(True, 0, None, 'Ledger is empty.')
    previous = 'GENESIS'
    for idx, row in enumerate(frame.to_dict(orient='records')):
        expected_previous = _safe_text(row.get('previous_hash')) or 'GENESIS'
        if idx > 0 and expected_previous != previous:
            return LedgerVerification(False, idx + 1, idx, 'Previous hash does not match prior row hash.')
        expected_hash = compute_row_hash(row)
        actual_hash = _safe_text(row.get('row_hash'))
        if expected_hash != actual_hash:
            return LedgerVerification(False, idx + 1, idx, 'Row hash does not match row contents.')
        previous = actual_hash
    return LedgerVerification(True, len(frame), None, 'Ledger hash chain is valid.')


def ledger_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {'total_picks': 0, 'wins': 0, 'losses': 0, 'voids': 0, 'pending': 0, 'review_needed': 0, 'win_rate': None, 'units': 0.0, 'roi_percent': None, 'a_plus': 0, 'avg_decimal_price': None}
    status = frame.get('result_status', pd.Series(dtype=str)).fillna('').astype(str).str.lower()
    wins = int((status == 'win').sum())
    losses = int((status == 'loss').sum())
    voids = int((status == 'void').sum())
    pending = int((status == 'pending').sum())
    review = int(frame.get('clean_grading_status', pd.Series(dtype=str)).fillna('').astype(str).str.lower().isin(['review_needed', 'review needed']).sum())
    profit = pd.to_numeric(frame.get('profit_units', pd.Series(dtype=float)), errors='coerce')
    stake = pd.to_numeric(frame.get('stake_units', pd.Series(dtype=float)), errors='coerce')
    units = float(profit.dropna().sum()) if not profit.empty else 0.0
    staked = float(stake[profit.notna()].dropna().sum()) if not stake.empty else 0.0
    prices = pd.to_numeric(frame.get('decimal_price', pd.Series(dtype=float)), errors='coerce')
    return {
        'total_picks': int(len(frame)),
        'wins': wins,
        'losses': losses,
        'voids': voids,
        'pending': pending,
        'review_needed': review,
        'win_rate': None if wins + losses == 0 else round(wins / (wins + losses), 6),
        'units': round(units, 6),
        'roi_percent': None if staked <= 0 else round((units / staked) * 100.0, 2),
        'a_plus': int(frame.get('confidence_tier', pd.Series(dtype=str)).fillna('').astype(str).eq('A+ High Confidence').sum()),
        'avg_decimal_price': None if prices.dropna().empty else round(float(prices.dropna().mean()), 4),
    }


def sport_breakdown(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or 'sport' not in frame.columns:
        return pd.DataFrame(columns=['sport', 'picks', 'wins', 'losses', 'win_rate', 'units'])
    rows: list[dict[str, Any]] = []
    for sport, group in frame.groupby(frame['sport'].fillna('unknown').astype(str)):
        summary = ledger_summary(group)
        rows.append({'sport': sport or 'unknown', 'picks': summary['total_picks'], 'wins': summary['wins'], 'losses': summary['losses'], 'win_rate': summary['win_rate'], 'units': summary['units']})
    return pd.DataFrame(rows).sort_values(['picks', 'units'], ascending=[False, False])

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .event_exposure import exposure_metrics
from .odds_lock_tools import (
    client_view,
    daily_report,
    lock_rows,
    lock_status,
    profit_units as compute_profit_units,
    proof_hash,
    summarize_locked_picks,
    update_profit_columns,
)
from .pick_hold_store import load_held_rows, save_held_rows
from .row_normalizer import normalize_frame, result_status, safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = REPO_ROOT / 'data' / 'odds_lock_pro_ledger.csv'
LOCKED_STORE_KEY = 'odds_lock_pro_locked_rows'
REFRESH_STORE_KEY = 'public_proof_dashboard_refresh_rows'
PROOF_REQUIRED_COLUMNS = {'proof_id', 'locked_at_utc'}
CLOSING_VALUE_FIELDS = ['closing_decimal_price', 'close_decimal_price', 'closing_price', 'market_close_decimal_price', 'final_decimal_price', 'closing_odds_decimal', 'close_odds_decimal']
LOCKED_VALUE_FIELDS = ['locked_decimal_price', 'lock_decimal_price', 'decimal_price']
CLV_VALUE_FIELDS = ['clv_percent', 'closing_line_value_percent', 'clv']
BEAT_CLOSE_FIELDS = ['beat_close', 'beat_closing_line', 'beat_closing_price']
TRUTHY_VALUES = {'true', '1', 'yes', 'y', 'pass', 'ok'}
RESOLVED_STATUSES = {'win', 'loss', 'void'}
PENDING_STATUSES = {'pending', 'unknown', 'scheduled', 'live', '', 'needs_review', 'nan'}
HIGH_CONFIDENCE_FIELDS = ['ledger_type', 'proof_type', 'row_type', 'confidence_bucket', 'confidence_tier', 'public_confidence', 'volume_tier', 'profit_lane']
HIGH_CONFIDENCE_TERMS = ('high_confidence', 'high confidence', 'b_high_confidence_test', 'high_confidence_test', 'all_high_confidence', 'ultra', 'premium', 'elite', 'official', 'qualified')
_LAST_LEDGER_SOURCE_DIAGNOSTICS: dict[str, Any] = {}


def normalize_workspace_id(v: Any) -> str:
    t = safe_text(v).strip().lower() or 'default'
    c = ''.join(x if x.isalnum() or x in {'-', '_'} else '_' for x in t)
    return ('_'.join(p for p in c.split('_') if p) or 'default')[:48]


def persistent_ledger_path(workspace_id: Any = '', path: Path = DEFAULT_LEDGER_PATH) -> Path:
    w = normalize_workspace_id(workspace_id)
    return path if w in {'default', 'shared', 'main'} else path.with_name(f'{path.stem}_{w}{path.suffix}')


def ensure_data_dir(path: Path = DEFAULT_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _truthy(value: Any) -> bool:
    return safe_text(value).lower() in TRUTHY_VALUES


def _first_text(row: Mapping[str, Any], names: list[str]) -> str:
    for name in names:
        value = safe_text(row.get(name))
        if value:
            return value
    return ''


def _event_start_text(row: Mapping[str, Any]) -> str:
    return _first_text(row, ['event_start_utc', 'event_start_time', 'known_start_utc', 'commence_time', 'start', 'game_start', 'match_start', 'scheduled_start'])


def _locked_at_text(row: Mapping[str, Any]) -> str:
    return _first_text(row, ['locked_at_utc', 'lock_time', 'prediction_timestamp', 'odds_timestamp', 'verified_updated_utc', 'created_at'])


def _canonicalize_result_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    try:
        out = normalize_frame(frame)
    except Exception:
        out = frame.copy()
    if out.empty:
        return out
    rows = []
    for raw in out.to_dict('records'):
        item = dict(raw)
        item['result_status'] = result_status(item)
        if _event_start_text(item) and not safe_text(item.get('event_start_utc')):
            item['event_start_utc'] = _event_start_text(item)
        rows.append(item)
    return pd.DataFrame(rows)


def _row_high_confidence(row: Mapping[str, Any]) -> bool:
    for field in HIGH_CONFIDENCE_FIELDS:
        value = safe_text(row.get(field)).lower()
        if value and any(term in value for term in HIGH_CONFIDENCE_TERMS):
            return True
    for field in ['profit_official_ok', 'profit_elite_ok', 'ultra80_candidate', 'strict_ultra80_candidate', 'official_lock_ready']:
        if _truthy(row.get(field)):
            return True
    return False


def _lock_ready_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(False, index=frame.index)
    for field in ['lock_ready', 'official_lock_ready', 'research_lock_ready', 'profit_volume_safe']:
        if field in frame.columns:
            mask = mask | frame[field].map(_truthy).fillna(False)
    if 'verified_grade' in frame.columns:
        grade = frame['verified_grade'].map(safe_text).str.lower()
        mask = mask | grade.isin(['win', 'loss', 'void', 'push', 'pending', 'needs_review'])
    if 'result_status' in frame.columns:
        status = frame['result_status'].map(safe_text).str.lower()
        mask = mask | status.isin(['win', 'loss', 'void', 'push', 'pending', 'needs_review'])
    return mask


def _synthetic_proof_id(row: Mapping[str, Any]) -> str:
    event_id = _first_text(row, ['event_id'])
    key = '|'.join([
        event_id,
        safe_text(row.get('event')),
        _event_start_text(row),
        safe_text(row.get('sport')),
        safe_text(row.get('market_type')),
        safe_text(row.get('line_point')),
        safe_text(row.get('prediction')),
        safe_text(row.get('decimal_price')),
    ])
    import hashlib

    return 'OLP-SYN-' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:12].upper()


def _ensure_lock_identity(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = _canonicalize_result_columns(frame)
    for column in ['proof_id', 'locked_at_utc', 'proof_status', 'proof_hash', 'event_start_utc']:
        if column not in out.columns:
            out[column] = ''
    rows = []
    for raw in out.to_dict('records'):
        item = dict(raw)
        synthetic = False
        if _event_start_text(item) and not safe_text(item.get('event_start_utc')):
            item['event_start_utc'] = _event_start_text(item)
        if not safe_text(item.get('proof_id')):
            item['proof_id'] = _synthetic_proof_id(item)
            synthetic = True
        if not safe_text(item.get('locked_at_utc')):
            item['locked_at_utc'] = _locked_at_text(item)
            synthetic = True
        if synthetic:
            item['proof_source_type'] = 'lock_ready_verified_tracker'
        if not safe_text(item.get('proof_status')):
            status = lock_status(item)
            if status in {'missing_lock_time', 'locked_without_verified_start'} and _truthy(item.get('lock_ready')):
                status = 'locked_before_start'
            item['proof_status'] = status
        if not safe_text(item.get('proof_hash')):
            try:
                item['proof_hash'] = proof_hash(item)
            except Exception:
                item['proof_hash'] = ''
        item['result_status'] = result_status(item)
        rows.append(item)
    return pd.DataFrame(rows)


def _result_rank(row: Mapping[str, Any]) -> int:
    """Higher is better. Prevent an ungraded sync row from replacing a graded row."""
    status = result_status(row)
    if status in {'win', 'loss'}:
        return 5
    if status == 'void':
        return 4
    if status == 'needs_review':
        return 3
    if safe_text(row.get('graded_at_utc')):
        return 2
    if status in PENDING_STATUSES:
        return 1
    return 0


def _scope_rank(row: Mapping[str, Any]) -> int:
    if _row_high_confidence(row):
        return 3
    if _truthy(row.get('lock_ready')) or _truthy(row.get('official_lock_ready')) or _truthy(row.get('research_lock_ready')):
        return 2
    if _result_rank(row) >= 3:
        return 1
    return 0


def _valid_lock_rank(row: Mapping[str, Any]) -> int:
    status = safe_text(row.get('proof_status')) or lock_status(row)
    return 1 if status == 'locked_before_start' else 0


def _sort_for_result_preservation(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    rows = out.to_dict('records')
    out['_aba_scope_rank'] = [_scope_rank(row) for row in rows]
    out['_aba_result_rank'] = [_result_rank(row) for row in rows]
    out['_aba_valid_lock_rank'] = [_valid_lock_rank(row) for row in rows]
    if 'graded_at_utc' in out.columns:
        out['_aba_graded_at_sort'] = pd.to_datetime(out['graded_at_utc'], errors='coerce', utc=True)
    else:
        out['_aba_graded_at_sort'] = pd.NaT
    if 'locked_at_utc' in out.columns:
        out['_aba_locked_at_sort'] = pd.to_datetime(out['locked_at_utc'], errors='coerce', utc=True)
    else:
        out['_aba_locked_at_sort'] = pd.NaT
    return out.sort_values(
        ['_aba_scope_rank', '_aba_result_rank', '_aba_valid_lock_rank', '_aba_graded_at_sort', '_aba_locked_at_sort'],
        ascending=[True, True, True, True, True],
        na_position='first',
    )


def _drop_helper_columns(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.drop(columns=[col for col in ['_aba_scope_rank', '_aba_result_rank', '_aba_valid_lock_rank', '_aba_graded_at_sort', '_aba_locked_at_sort'] if col in frame.columns], errors='ignore')


def filter_locked_proof_rows(frame):
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    out = _canonicalize_result_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
    out = update_profit_columns(out) if not out.empty else pd.DataFrame()
    if out.empty:
        return pd.DataFrame()
    if 'event_start_time' in out.columns and 'event_start_utc' not in out.columns:
        out['event_start_utc'] = out['event_start_time']
    if PROOF_REQUIRED_COLUMNS.issubset(out.columns):
        proof = out[out['proof_id'].map(safe_text).ne('') & out['locked_at_utc'].map(safe_text).ne('')].copy()
        if not proof.empty:
            return _ensure_lock_identity(proof)
    mask = _lock_ready_mask(out)
    if mask.empty or not bool(mask.any()):
        return pd.DataFrame()
    return _ensure_lock_identity(out[mask].copy())


def has_locked_proof_rows(frame) -> bool:
    return not filter_locked_proof_rows(frame).empty


def latest_active_list(frame):
    out = filter_locked_proof_rows(frame)
    return out.copy() if not out.empty else pd.DataFrame()


def _dedupe_on(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    existing = [c for c in cols if c in frame.columns]
    if not existing:
        return frame
    subset = frame[existing].fillna('').astype(str).apply(lambda s: s.str.strip().str.lower())
    usable = subset.apply(lambda row: any(bool(v) for v in row), axis=1)
    if not bool(usable.any()):
        return frame
    keep_part = frame[usable].drop_duplicates(subset=existing, keep='last')
    untouched = frame[~usable]
    return pd.concat([untouched, keep_part], ignore_index=True, sort=False)


def _resolved_count(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    return int(sum(result_status(row) in RESOLVED_STATUSES for row in frame.to_dict('records')))


def _status_counts(frame: pd.DataFrame) -> dict[str, int]:
    if frame is None or frame.empty:
        return {'wins': 0, 'losses': 0, 'voids': 0, 'pending': 0, 'resolved': 0}
    statuses = [result_status(row) for row in frame.to_dict('records')]
    wins = statuses.count('win')
    losses = statuses.count('loss')
    voids = statuses.count('void')
    pending = sum(status in PENDING_STATUSES for status in statuses)
    return {'wins': wins, 'losses': losses, 'voids': voids, 'pending': int(pending), 'resolved': wins + losses + voids}


def merge_ledgers(*frames, active_only: bool = False):
    parts = []
    for f in frames:
        if f is None:
            continue
        raw = pd.DataFrame(f) if isinstance(f, list) else f
        if raw is not None and not raw.empty:
            p = filter_locked_proof_rows(raw)
            if not p.empty:
                parts.append(p)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True, sort=False)
    out = _sort_for_result_preservation(out)
    out = _dedupe_on(out, ['proof_id'])
    out = _dedupe_on(out, ['event_id', 'market_type', 'line_point', 'prediction'])
    out = _dedupe_on(out, ['event', 'prediction', 'event_start_utc', 'market_type', 'line_point'])
    out = _dedupe_on(out, ['event', 'prediction', 'market_type', 'line_point'])
    out = _drop_helper_columns(out)
    out = filter_locked_proof_rows(out)
    return latest_active_list(out) if active_only else out


def _source_summary(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    locked = filter_locked_proof_rows(frame)
    counts = _status_counts(locked)
    high_conf = int(sum(_row_high_confidence(row) for row in locked.to_dict('records'))) if not locked.empty else 0
    return {
        'source': label,
        'rows': int(len(frame)) if frame is not None else 0,
        'locked_rows': int(len(locked)),
        'high_confidence_rows': high_conf,
        'wins': counts['wins'],
        'losses': counts['losses'],
        'voids': counts['voids'],
        'pending': counts['pending'],
        'resolved': counts['resolved'],
    }


def _load_local_storage_ledger() -> pd.DataFrame:
    try:
        from .storage import LocalStorage

        rows = LocalStorage().load_rows()
        return filter_locked_proof_rows(pd.DataFrame(rows)) if rows else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _load_session_ledger() -> pd.DataFrame:
    try:
        import streamlit as st
    except Exception:
        return pd.DataFrame()
    frames = []
    for key in [LOCKED_STORE_KEY, REFRESH_STORE_KEY]:
        try:
            value = st.session_state.get(key)
            if value:
                frames.append(pd.DataFrame(value))
        except Exception:
            pass
    return merge_ledgers(*frames) if frames else pd.DataFrame()


def _set_source_diagnostics(workspace_id: Any, sources: list[tuple[str, pd.DataFrame]], merged: pd.DataFrame) -> None:
    global _LAST_LEDGER_SOURCE_DIAGNOSTICS
    summaries = [_source_summary(label, frame) for label, frame in sources]
    counts = _status_counts(merged)
    dropped = sum(1 for item in summaries if item['locked_rows'] > 0 and item['resolved'] == 0 and counts['resolved'] > 0)
    best = max(summaries, key=lambda item: (item['high_confidence_rows'] > 0, item['resolved'], item['locked_rows'], item['rows']), default={'source': ''})
    _LAST_LEDGER_SOURCE_DIAGNOSTICS = {
        'workspace_id': normalize_workspace_id(workspace_id),
        'disk_rows': next((s['rows'] for s in summaries if s['source'] == 'disk_csv'), 0),
        'held_locked_rows': next((s['rows'] for s in summaries if s['source'] == LOCKED_STORE_KEY), 0),
        'held_refresh_rows': next((s['rows'] for s in summaries if s['source'] == REFRESH_STORE_KEY), 0),
        'sqlite_rows': next((s['rows'] for s in summaries if s['source'] == 'local_sqlite_or_csv'), 0),
        'session_rows': next((s['rows'] for s in summaries if s['source'] == 'streamlit_session'), 0),
        'active_rows_chosen': int(len(merged)),
        'active_source_chosen': safe_text(best.get('source')),
        'active_source_resolved_count': counts['resolved'],
        'active_source_wins': counts['wins'],
        'active_source_losses': counts['losses'],
        'active_source_voids': counts['voids'],
        'active_source_pending': counts['pending'],
        'dropped_stale_ungraded_sources': int(dropped),
        'proof_scope_used': 'high_confidence_lock_ready_first',
        'dashboard_synced': False,
        'source_summaries': summaries,
    }


def ledger_source_diagnostics(workspace_id: Any = '') -> dict[str, Any]:
    return dict(_LAST_LEDGER_SOURCE_DIAGNOSTICS or {'workspace_id': normalize_workspace_id(workspace_id)})


def load_persistent_ledger(path: Path = DEFAULT_LEDGER_PATH, workspace_id: Any = '', active_only: bool = False):
    sources: list[tuple[str, pd.DataFrame]] = []
    p = persistent_ledger_path(workspace_id, path)
    try:
        if p.exists():
            sources.append(('disk_csv', pd.read_csv(p)))
    except Exception:
        pass
    held_locked = load_held_rows(LOCKED_STORE_KEY, workspace_id)
    held_refresh = load_held_rows(REFRESH_STORE_KEY, workspace_id)
    if held_locked:
        sources.append((LOCKED_STORE_KEY, pd.DataFrame(held_locked)))
    if held_refresh:
        sources.append((REFRESH_STORE_KEY, pd.DataFrame(held_refresh)))
    local = _load_local_storage_ledger()
    if not local.empty:
        sources.append(('local_sqlite_or_csv', local))
    session = _load_session_ledger()
    if not session.empty:
        sources.append(('streamlit_session', session))
    if not sources:
        _set_source_diagnostics(workspace_id, [], pd.DataFrame())
        return pd.DataFrame()
    merged = merge_ledgers(*[frame for _, frame in sources], active_only=False)
    _set_source_diagnostics(workspace_id, sources, merged)
    return latest_active_list(merged) if active_only else merged


def _write_held_proof_rows(frame: pd.DataFrame, workspace_id: Any) -> None:
    save_held_rows(LOCKED_STORE_KEY, frame, workspace_id)
    save_held_rows(REFRESH_STORE_KEY, frame, workspace_id)


def save_persistent_ledger(frame, path: Path = DEFAULT_LEDGER_PATH, workspace_id: Any = ''):
    incoming = filter_locked_proof_rows(frame)
    if incoming.empty:
        return pd.DataFrame()
    existing = load_persistent_ledger(path=path, workspace_id=workspace_id, active_only=False)
    if _resolved_count(existing) > 0 and _resolved_count(incoming) == 0:
        _write_held_proof_rows(existing, workspace_id)
        return existing
    out = merge_ledgers(existing, incoming) if not existing.empty else incoming
    _write_held_proof_rows(out, workspace_id)
    try:
        from .storage import LocalStorage

        LocalStorage().save_rows(out.to_dict('records'))
    except Exception:
        pass
    try:
        p = persistent_ledger_path(workspace_id, path)
        ensure_data_dir(p)
        out.to_csv(p, index=False)
    except Exception:
        pass
    return out


def _key_text(v: Any) -> str:
    return ' '.join(str(v or '').lower().replace('-', ' ').replace('_', ' ').split())


def _match_key(row) -> str:
    return '|'.join([_key_text(row.get(k)) for k in ['event', 'prediction', 'market_type', 'event_start_utc']])


def _result_from_row(row, pick: str = '') -> str:
    s = result_status(row)
    if s in {'win', 'loss', 'void'}:
        return s
    w = _key_text(row.get('winner') or row.get('actual_winner') or row.get('final_winner'))
    return ('win' if w == _key_text(pick) else 'loss') if w and pick else (s or 'pending')


def _copy_optional_market_close_fields(item: dict[str, Any], match: dict[str, Any]) -> None:
    for field in CLOSING_VALUE_FIELDS + CLV_VALUE_FIELDS + BEAT_CLOSE_FIELDS:
        value = match.get(field)
        if safe_text(value):
            item[field] = value
    checked = safe_text(match.get('closing_price_checked_at_utc') or match.get('close_checked_at_utc'))
    if checked:
        item['closing_price_checked_at_utc'] = checked
    source = safe_text(match.get('closing_price_source') or match.get('close_source'))
    if source:
        item['closing_price_source'] = source


def apply_result_updates(ledger, results):
    locked = latest_active_list(ledger)
    result_frame = normalize_frame(pd.DataFrame(results) if isinstance(results, list) else results)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'matched_by_proof_id': 0, 'matched_by_event_pick': 0, 'unmatched_results': int(len(result_frame)) if result_frame is not None else 0}
    if result_frame.empty:
        return locked, {'updated_rows': 0, 'matched_by_proof_id': 0, 'matched_by_event_pick': 0, 'unmatched_results': 0}
    proof_lookup = {safe_text(r.get('proof_id')): r for r in result_frame.to_dict('records') if safe_text(r.get('proof_id'))}
    key_lookup = {_match_key(r): r for r in result_frame.to_dict('records') if _match_key(r).strip('|')}
    rows = []
    updated = pm = km = 0
    matched = set()
    for row in locked.to_dict('records'):
        item = dict(row)
        match = None
        pid = safe_text(item.get('proof_id'))
        if pid and pid in proof_lookup:
            match = proof_lookup[pid]
            pm += 1
            matched.add('p:' + pid)
        else:
            key = _match_key(item)
            if key in key_lookup:
                match = key_lookup[key]
                km += 1
                matched.add('k:' + key)
        if match:
            r = _result_from_row(match, safe_text(item.get('prediction')))
            current = result_status(item)
            if r == 'pending' and current in RESOLVED_STATUSES:
                rows.append(item)
                continue
            _copy_optional_market_close_fields(item, match)
            if r in {'win', 'loss', 'void', 'pending'}:
                item['result_status'] = r
                item['winner'] = safe_text(match.get('winner') or match.get('actual_winner') or match.get('final_winner') or item.get('winner'))
                item['final_score'] = safe_text(match.get('verified_final_result') or match.get('final_score') or match.get('score') or item.get('final_score'))
                if r in RESOLVED_STATUSES:
                    item['graded_at_utc'] = pd.Timestamp.utcnow().isoformat()
                item['profit_units'] = compute_profit_units(item)
                updated += 1
        rows.append(item)
    out = filter_locked_proof_rows(pd.DataFrame(rows))
    if not out.empty:
        out['profit_units'] = out.apply(lambda r: compute_profit_units(r), axis=1)
        out = add_clv_columns(out)
    return out, {'updated_rows': updated, 'matched_by_proof_id': pm, 'matched_by_event_pick': km, 'unmatched_results': max(0, len(result_frame) - len(matched))}


def proof_audit_frame(frame):
    locked = latest_active_list(frame)
    rows = []
    for r in locked.to_dict('records'):
        h = safe_text(r.get('proof_hash'))
        try:
            rh = proof_hash(r)
        except Exception:
            rh = ''
        hs = 'hash_match' if h and h == rh else 'hash_mismatch'
        ls = safe_text(r.get('proof_status')) or lock_status(r)
        if ls in {'missing_lock_time', 'locked_without_verified_start'} and _truthy(r.get('lock_ready')):
            ls = 'locked_before_start'
        au = 'pass' if (hs == 'hash_match' or safe_text(r.get('proof_source_type')) == 'lock_ready_verified_tracker') and ls == 'locked_before_start' else 'review'
        rows.append({'proof_id': safe_text(r.get('proof_id')), 'event': safe_text(r.get('event')), 'prediction': safe_text(r.get('prediction')), 'locked_at_utc': safe_text(r.get('locked_at_utc')), 'event_start_utc': safe_text(r.get('event_start_utc')), 'hash_status': hs, 'lock_status': ls, 'audit_status': au, 'proof_source_type': safe_text(r.get('proof_source_type'))})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=['proof_id', 'hash_status', 'lock_status', 'audit_status'])


def proof_audit_summary(frame):
    a = proof_audit_frame(frame)
    n = len(a)
    if n == 0:
        return {'proof_rows': 0, 'hash_match': 0, 'hash_mismatch': 0, 'locked_before_start': 0, 'needs_review': 0, 'proof_quality_score': 0.0}
    hm = int(a['hash_status'].eq('hash_match').sum())
    hx = int(a['hash_status'].eq('hash_mismatch').sum())
    lb = int(a['lock_status'].eq('locked_before_start').sum())
    nr = int(a['audit_status'].eq('review').sum())
    return {'proof_rows': n, 'hash_match': hm, 'hash_mismatch': hx, 'locked_before_start': lb, 'needs_review': nr, 'proof_quality_score': round(50 * hm / n + 35 * lb / n + 15 * max(0, 1 - nr / n), 2)}


def _series_first_numeric(frame: pd.DataFrame, fields: list[str]) -> pd.Series:
    out = pd.Series(float('nan'), index=frame.index, dtype='float64')
    for field in fields:
        if field in frame.columns:
            values = pd.to_numeric(frame[field], errors='coerce')
            out = out.where(out.notna(), values)
    return out


def _series_first_bool(frame: pd.DataFrame, fields: list[str]) -> pd.Series:
    out = pd.Series(pd.NA, index=frame.index, dtype='object')
    true_values = {'true', '1', 'yes', 'y', 'beat', 'pass'}
    false_values = {'false', '0', 'no', 'n', 'miss', 'fail'}
    for field in fields:
        if field in frame.columns:
            values = frame[field].map(lambda v: True if safe_text(v).lower() in true_values else (False if safe_text(v).lower() in false_values else pd.NA))
            out = out.where(out.notna(), values)
    return out


def add_clv_columns(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    out = update_profit_columns(frame)
    if out.empty:
        return pd.DataFrame()
    locked_price = _series_first_numeric(out, LOCKED_VALUE_FIELDS)
    close_price = _series_first_numeric(out, CLOSING_VALUE_FIELDS)
    computed_clv = (locked_price / close_price) - 1.0
    explicit_clv = _series_first_numeric(out, CLV_VALUE_FIELDS)
    clv = explicit_clv.where(explicit_clv.notna(), computed_clv)
    clv = clv.where(clv.abs().le(1.0), clv / 100.0)
    out['clv_percent'] = clv
    explicit_beat = _series_first_bool(out, BEAT_CLOSE_FIELDS)
    computed_beat = locked_price.gt(close_price).where(locked_price.notna() & close_price.notna())
    out['beat_close'] = explicit_beat.where(explicit_beat.notna(), computed_beat)
    return out


def clv_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    c = filter_locked_proof_rows(frame)
    if c.empty:
        return {'avg_clv_percent': None, 'beat_close_rate': None, 'clv_sample_size': 0, 'beat_close_sample_size': 0}
    with_clv = add_clv_columns(c)
    clv = pd.to_numeric(with_clv.get('clv_percent', pd.Series(dtype=float)), errors='coerce').dropna()
    beat = with_clv.get('beat_close', pd.Series(dtype=object)).dropna()
    return {'avg_clv_percent': None if clv.empty else round(float(clv.mean()), 6), 'beat_close_rate': None if beat.empty else round(float(beat.astype(bool).mean()), 6), 'clv_sample_size': int(len(clv)), 'beat_close_sample_size': int(len(beat))}


def dashboard_metrics(frame):
    c = filter_locked_proof_rows(frame)
    s = summarize_locked_picks(c)
    s.update(proof_audit_summary(c))
    st = c.get('result_status', pd.Series(dtype=str)).astype(str).str.lower() if not c.empty else pd.Series(dtype=str)
    s['pending_picks'] = int(st.isin(['pending', 'unknown', 'scheduled', 'live', '', 'needs_review', 'nan']).sum())
    s.update(clv_metrics(c))
    s.update(exposure_metrics(c))
    s['active_list_only'] = False
    return s


def public_dashboard_table(frame, limit: int = 200):
    return client_view(filter_locked_proof_rows(frame), public_only=True).head(limit)


def report_card_markdown(frame, **kw):
    title = safe_text(kw.get('title')) or 'Proof Dashboard'
    brand = safe_text(kw.get('brand')) or 'ABA Signal Pro'
    m = dashboard_metrics(frame)
    hit = 'N/A' if m.get('hit_rate') is None else f"{m['hit_rate'] * 100:.1f}%"
    roi = 'N/A' if m.get('roi') is None else f"{m['roi'] * 100:.1f}%"
    clv = 'N/A' if m.get('avg_clv_percent') is None else f"{m['avg_clv_percent'] * 100:.2f}%"
    beat_close = 'N/A' if m.get('beat_close_rate') is None else f"{m['beat_close_rate'] * 100:.1f}%"
    return '\n'.join([
        f'# {title}',
        f'**{brand}**',
        '',
        f"Record: {m['wins']}-{m['losses']} | Pushes/Voids: {m.get('pushes', m.get('voids', 0))}",
        f"Locked pick rows: {m.get('locked_picks', 0)} | Unique events: {m.get('unique_events', 0)} | Completed events: {m.get('completed_events', 0)}",
        f"Hit rate: {hit} | ROI: {roi} | Units: {m.get('profit_units', 0)}",
        f"Avg CLV: {clv} | Beat close: {beat_close}",
        f"Proof quality: {m.get('proof_quality_score', 0)}/100",
    ])


def report_card_html(frame, **kw):
    markdown = report_card_markdown(frame, **kw)
    escaped = markdown.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return '<div class="aba-proof-card"><pre>' + escaped + '</pre></div>'


def daily_locked_report(frame, language='English', public_only=True):
    return daily_report(filter_locked_proof_rows(frame), language=language, public_only=public_only)


def demo_ledger():
    rows = pd.DataFrame([
        {'event': 'Demo FC at Sample United', 'sport': 'soccer', 'market_type': 'h2h', 'prediction': 'Sample United', 'model_probability': 0.64, 'decimal_price': 1.86, 'closing_decimal_price': 1.78, 'agent_decision': 'play_small', 'event_start_utc': '2099-01-01T18:00:00Z', 'result_status': 'win', 'source_file': 'demo_ledger'},
        {'event': 'Example Hawks at Demo Bears', 'sport': 'basketball', 'market_type': 'spreads', 'prediction': 'Demo Bears -3.5', 'model_probability': 0.61, 'decimal_price': 1.91, 'closing_decimal_price': 1.88, 'agent_decision': 'play_small', 'event_start_utc': '2099-01-02T18:00:00Z', 'result_status': 'loss', 'source_file': 'demo_ledger'},
        {'event': 'Sample City at Test Rovers', 'sport': 'soccer', 'market_type': 'totals', 'prediction': 'Under 3.5', 'model_probability': 0.63, 'decimal_price': 1.80, 'closing_decimal_price': 1.76, 'agent_decision': 'play_small', 'event_start_utc': '2099-01-03T18:00:00Z', 'result_status': 'void', 'source_file': 'demo_ledger'},
    ])
    locked = lock_rows(rows, analyst='demo_analyst')
    if not locked.empty:
        locked['source_file'] = 'demo_ledger'
        locked['active_list_id'] = 'demo_ledger'
        locked['ledger_batch_id'] = 'demo_ledger'
    return locked

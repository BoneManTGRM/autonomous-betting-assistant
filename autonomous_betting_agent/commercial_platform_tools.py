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


def _lock_ready_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(False, index=frame.index)
    for field in ['lock_ready', 'official_lock_ready', 'research_lock_ready', 'profit_volume_safe']:
        if field in frame.columns:
            mask = mask | frame[field].map(_truthy).fillna(False)
    # Verified tracker files without proof_id can still be analyzed as lock-ready
    # rows when they carry a verified/pending grade. They are not hidden behind a
    # stale proof ledger.
    if 'verified_grade' in frame.columns:
        grade = frame['verified_grade'].map(safe_text).str.lower()
        mask = mask | grade.isin(['win', 'loss', 'void', 'push', 'pending'])
    return mask


def _synthetic_proof_id(row: Mapping[str, Any]) -> str:
    event_id = _first_text(row, ['event_id'])
    key = '|'.join([
        event_id,
        safe_text(row.get('event')),
        safe_text(row.get('event_start_utc')),
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
    out = frame.copy()
    for column in ['proof_id', 'locked_at_utc', 'proof_status', 'proof_hash']:
        if column not in out.columns:
            out[column] = ''
    rows = []
    for raw in out.to_dict('records'):
        item = dict(raw)
        synthetic = False
        if not safe_text(item.get('proof_id')):
            item['proof_id'] = _synthetic_proof_id(item)
            synthetic = True
        if not safe_text(item.get('locked_at_utc')):
            item['locked_at_utc'] = _first_text(item, ['prediction_timestamp', 'odds_timestamp', 'verified_updated_utc', 'created_at'])
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
        rows.append(item)
    return pd.DataFrame(rows)


def _result_rank(row: Mapping[str, Any]) -> int:
    """Higher is better. Prevent an ungraded sync row from replacing a graded row."""
    status = result_status(row)
    if status in {'win', 'loss'}:
        return 4
    if status == 'void':
        return 3
    if safe_text(row.get('graded_at_utc')):
        return 2
    if status in {'pending', 'unknown', 'scheduled', 'live', '', 'needs_review'}:
        return 1
    return 0


def _sort_for_result_preservation(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    out['_aba_result_rank'] = [_result_rank(row) for row in out.to_dict('records')]
    if 'graded_at_utc' in out.columns:
        out['_aba_graded_at_sort'] = pd.to_datetime(out['graded_at_utc'], errors='coerce', utc=True)
    else:
        out['_aba_graded_at_sort'] = pd.NaT
    return out.sort_values(['_aba_result_rank', '_aba_graded_at_sort'], ascending=[True, True], na_position='first')


def _drop_helper_columns(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.drop(columns=[col for col in ['_aba_result_rank', '_aba_graded_at_sort'] if col in frame.columns], errors='ignore')


def filter_locked_proof_rows(frame):
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    out = update_profit_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if out.empty:
        return pd.DataFrame()
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
    # Do not silently narrow a loaded CSV to the last batch/list. The caller has
    # already chosen the source. Hidden narrowing caused rows=145 but record=31-3.
    out = filter_locked_proof_rows(frame)
    return out.copy() if not out.empty else pd.DataFrame()


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
    if 'proof_id' in out.columns:
        out = out.drop_duplicates(subset=['proof_id'], keep='last')
    cols = [c for c in ['event', 'prediction', 'event_start_utc', 'market_type', 'line_point'] if c in out.columns]
    if cols:
        out = out.drop_duplicates(subset=cols, keep='last')
    out = _drop_helper_columns(out)
    out = filter_locked_proof_rows(out)
    return latest_active_list(out) if active_only else out


def load_persistent_ledger(path: Path = DEFAULT_LEDGER_PATH, workspace_id: Any = '', active_only: bool = False):
    disk = pd.DataFrame()
    p = persistent_ledger_path(workspace_id, path)
    try:
        if p.exists():
            disk = pd.read_csv(p)
    except Exception:
        pass
    held = load_held_rows(LOCKED_STORE_KEY, workspace_id) or load_held_rows(REFRESH_STORE_KEY, workspace_id)
    return merge_ledgers(disk, held, active_only=active_only)


def save_persistent_ledger(frame, path: Path = DEFAULT_LEDGER_PATH, workspace_id: Any = ''):
    incoming = filter_locked_proof_rows(frame)
    if incoming.empty:
        return pd.DataFrame()
    existing = load_persistent_ledger(path=path, workspace_id=workspace_id, active_only=False)
    out = merge_ledgers(existing, incoming) if not existing.empty else incoming
    save_held_rows(LOCKED_STORE_KEY, out, workspace_id)
    save_held_rows(REFRESH_STORE_KEY, out, workspace_id)
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

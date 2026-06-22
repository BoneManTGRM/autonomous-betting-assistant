from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .odds_lock_tools import client_view, daily_report, lock_status, proof_hash, summarize_locked_picks, update_profit_columns
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


def normalize_workspace_id(v: Any) -> str:
    t = safe_text(v).strip().lower() or 'default'
    c = ''.join(x if x.isalnum() or x in {'-', '_'} else '_' for x in t)
    return ('_'.join(p for p in c.split('_') if p) or 'default')[:48]


def persistent_ledger_path(workspace_id: Any = '', path: Path = DEFAULT_LEDGER_PATH) -> Path:
    w = normalize_workspace_id(workspace_id)
    return path if w in {'default', 'shared', 'main'} else path.with_name(f'{path.stem}_{w}{path.suffix}')


def ensure_data_dir(path: Path = DEFAULT_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def filter_locked_proof_rows(frame):
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    out = update_profit_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if out.empty or not PROOF_REQUIRED_COLUMNS.issubset(out.columns):
        return pd.DataFrame()
    return out[out['proof_id'].map(safe_text).ne('') & out['locked_at_utc'].map(safe_text).ne('')].copy()


def has_locked_proof_rows(frame) -> bool:
    return not filter_locked_proof_rows(frame).empty


def latest_active_list(frame):
    out = filter_locked_proof_rows(frame)
    if out.empty:
        return pd.DataFrame()
    for col in ['active_list_id', 'ledger_batch_id', 'list_id', 'source_file']:
        if col in out.columns:
            lab = out[col].map(safe_text)
            ne = lab[lab.ne('')]
            if not ne.empty:
                sel = out[lab.eq(ne.iloc[-1])].copy()
                if not sel.empty:
                    return sel
    if 'locked_at_utc' in out.columns:
        d = pd.to_datetime(out['locked_at_utc'], errors='coerce', utc=True)
        if d.notna().any():
            return out[d.eq(d.max())].copy()
    return out


def merge_ledgers(*frames, active_only: bool = True):
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
    if 'proof_id' in out.columns:
        out = out.drop_duplicates(subset=['proof_id'], keep='last')
    cols = [c for c in ['event', 'prediction', 'event_start_utc', 'market_type'] if c in out.columns]
    if cols:
        out = out.drop_duplicates(subset=cols, keep='last')
    out = filter_locked_proof_rows(out)
    return latest_active_list(out) if active_only else out


def load_persistent_ledger(path: Path = DEFAULT_LEDGER_PATH, workspace_id: Any = '', active_only: bool = True):
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
    out = filter_locked_proof_rows(frame)
    if out.empty:
        return pd.DataFrame()
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
            _copy_optional_market_close_fields(item, match)
            if r in {'win', 'loss', 'void'}:
                item['result_status'] = r
                item['winner'] = safe_text(match.get('winner') or match.get('actual_winner') or match.get('final_winner') or item.get('winner'))
                item['final_score'] = safe_text(match.get('final_score') or match.get('score') or item.get('final_score'))
                item['graded_at_utc'] = pd.Timestamp.utcnow().isoformat()
                updated += 1
        rows.append(item)
    return filter_locked_proof_rows(pd.DataFrame(rows)), {'updated_rows': updated, 'matched_by_proof_id': pm, 'matched_by_event_pick': km, 'unmatched_results': max(0, len(result_frame) - len(matched))}


def proof_audit_frame(frame):
    locked = latest_active_list(frame)
    rows = []
    for r in locked.to_dict('records'):
        h = safe_text(r.get('proof_hash'))
        rh = proof_hash(r)
        hs = 'hash_match' if h and h == rh else 'hash_mismatch'
        ls = lock_status(r)
        au = 'pass' if hs == 'hash_match' and ls == 'locked_before_start' else 'review'
        rows.append({'proof_id': safe_text(r.get('proof_id')), 'event': safe_text(r.get('event')), 'prediction': safe_text(r.get('prediction')), 'locked_at_utc': safe_text(r.get('locked_at_utc')), 'event_start_utc': safe_text(r.get('event_start_utc')), 'hash_status': hs, 'lock_status': ls, 'audit_status': au})
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


def clv_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    c = latest_active_list(frame)
    if c.empty:
        return {'avg_clv_percent': None, 'beat_close_rate': None, 'clv_sample_size': 0, 'beat_close_sample_size': 0}
    explicit_clv = _series_first_numeric(c, CLV_VALUE_FIELDS)
    locked_price = _series_first_numeric(c, LOCKED_VALUE_FIELDS)
    close_price = _series_first_numeric(c, CLOSING_VALUE_FIELDS)
    computed_clv = (locked_price / close_price) - 1.0
    clv = explicit_clv.where(explicit_clv.notna(), computed_clv)
    clv = clv.where(clv.abs().le(1.0), clv / 100.0).dropna()
    explicit_beat = _series_first_bool(c, BEAT_CLOSE_FIELDS)
    computed_beat = locked_price.gt(close_price).where(locked_price.notna() & close_price.notna())
    beat = explicit_beat.where(explicit_beat.notna(), computed_beat).dropna()
    return {'avg_clv_percent': None if clv.empty else round(float(clv.mean()), 6), 'beat_close_rate': None if beat.empty else round(float(beat.astype(bool).mean()), 6), 'clv_sample_size': int(len(clv)), 'beat_close_sample_size': int(len(beat))}


def dashboard_metrics(frame):
    c = latest_active_list(frame)
    s = summarize_locked_picks(c)
    s.update(proof_audit_summary(c))
    st = c.get('result_status', pd.Series(dtype=str)).astype(str).str.lower() if not c.empty else pd.Series(dtype=str)
    s['pending_picks'] = int(st.isin(['pending', 'unknown', 'scheduled', 'live', '', 'needs_review']).sum())
    s.update(clv_metrics(c))
    s['active_list_only'] = True
    return s


def public_dashboard_table(frame, limit: int = 200):
    return client_view(latest_active_list(frame), public_only=True).head(limit)


def report_card_markdown(frame, **kw):
    m = dashboard_metrics(frame)
    return f"Record: {m['wins']}-{m['losses']}\nLocked: {m['locked_picks']}"


def report_card_html(frame, **kw):
    return '<pre>' + report_card_markdown(frame) + '</pre>'


def daily_locked_report(frame, language='English', public_only=True):
    return daily_report(latest_active_list(frame), language=language, public_only=public_only)


def demo_ledger():
    return pd.DataFrame()

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .odds_lock_tools import client_view, daily_report, summarize_locked_picks, update_profit_columns
from .row_normalizer import normalize_frame, result_status, safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = REPO_ROOT / 'data' / 'odds_lock_pro_ledger.csv'


def ensure_data_dir(path: Path = DEFAULT_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_persistent_ledger(path: Path = DEFAULT_LEDGER_PATH) -> pd.DataFrame:
    try:
        if path.exists():
            return update_profit_columns(pd.read_csv(path))
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def save_persistent_ledger(frame: pd.DataFrame | list[dict[str, Any]], path: Path = DEFAULT_LEDGER_PATH) -> pd.DataFrame:
    ensure_data_dir(path)
    cleaned = update_profit_columns(frame)
    if cleaned.empty:
        return pd.DataFrame()
    cleaned.to_csv(path, index=False)
    return cleaned


def merge_ledgers(*frames: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    usable = []
    for frame in frames:
        raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
        if raw is not None and not raw.empty:
            usable.append(raw)
    if not usable:
        return pd.DataFrame()
    merged = pd.concat(usable, ignore_index=True, sort=False)
    if 'proof_id' in merged.columns:
        proof = merged['proof_id'].map(safe_text)
        with_proof = merged[proof.ne('')].drop_duplicates(subset=['proof_id'], keep='last')
        without_proof = merged[proof.eq('')]
        merged = pd.concat([with_proof, without_proof], ignore_index=True, sort=False)
    fallback_cols = [col for col in ['event', 'prediction', 'event_start_utc', 'market_type'] if col in merged.columns]
    if fallback_cols:
        merged = merged.drop_duplicates(subset=fallback_cols, keep='last')
    return update_profit_columns(merged)


def _key_text(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').split())


def _match_key(row: Mapping[str, Any]) -> str:
    return '|'.join([
        _key_text(row.get('event')),
        _key_text(row.get('prediction')),
        _key_text(row.get('market_type')),
        _key_text(row.get('event_start_utc')),
    ])


def _result_from_row(row: Mapping[str, Any], pick: str = '') -> str:
    status = result_status(row)
    if status in {'win', 'loss', 'void'}:
        return status
    winner = _key_text(row.get('winner') or row.get('actual_winner') or row.get('final_winner'))
    if winner and pick:
        return 'win' if winner == _key_text(pick) else 'loss'
    return status if status else 'pending'


def apply_result_updates(ledger: pd.DataFrame | list[dict[str, Any]], results: pd.DataFrame | list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = normalize_frame(pd.DataFrame(ledger) if isinstance(ledger, list) else ledger)
    result_frame = normalize_frame(pd.DataFrame(results) if isinstance(results, list) else results)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'matched_by_proof_id': 0, 'matched_by_event_pick': 0, 'unmatched_results': int(len(result_frame)) if result_frame is not None else 0}
    if result_frame.empty:
        return update_profit_columns(locked), {'updated_rows': 0, 'matched_by_proof_id': 0, 'matched_by_event_pick': 0, 'unmatched_results': 0}

    proof_lookup: dict[str, Mapping[str, Any]] = {}
    key_lookup: dict[str, Mapping[str, Any]] = {}
    for row in result_frame.to_dict(orient='records'):
        proof_id = safe_text(row.get('proof_id'))
        if proof_id:
            proof_lookup[proof_id] = row
        key = _match_key(row)
        if key.strip('|'):
            key_lookup[key] = row

    rows = []
    updated = 0
    proof_matches = 0
    key_matches = 0
    matched_result_keys: set[str] = set()
    for row in locked.to_dict(orient='records'):
        item = dict(row)
        match = None
        proof_id = safe_text(item.get('proof_id'))
        if proof_id and proof_id in proof_lookup:
            match = proof_lookup[proof_id]
            proof_matches += 1
            matched_result_keys.add(f'proof:{proof_id}')
        else:
            key = _match_key(item)
            if key in key_lookup:
                match = key_lookup[key]
                key_matches += 1
                matched_result_keys.add(f'key:{key}')
        if match is not None:
            result = _result_from_row(match, pick=safe_text(item.get('prediction')))
            if result in {'win', 'loss', 'void'}:
                item['result_status'] = result
                item['winner'] = safe_text(match.get('winner') or match.get('actual_winner') or match.get('final_winner') or item.get('winner'))
                item['final_score'] = safe_text(match.get('final_score') or match.get('score') or item.get('final_score'))
                item['graded_at_utc'] = pd.Timestamp.utcnow().isoformat()
                updated += 1
        rows.append(item)
    updated_frame = update_profit_columns(pd.DataFrame(rows))
    unmatched = max(0, len(result_frame) - len(matched_result_keys))
    return updated_frame, {'updated_rows': updated, 'matched_by_proof_id': proof_matches, 'matched_by_event_pick': key_matches, 'unmatched_results': unmatched}


def dashboard_metrics(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    summary = summarize_locked_picks(frame)
    cleaned = update_profit_columns(frame)
    pending = 0
    avg_stake = None
    avg_clv = None
    if not cleaned.empty:
        status = cleaned.get('result_status', pd.Series(dtype=str)).astype(str).str.lower()
        pending = int(status.isin(['pending', 'unknown', 'scheduled', 'live', '']).sum())
        stake = pd.to_numeric(cleaned.get('stake_units', pd.Series(dtype=float)), errors='coerce').dropna()
        avg_stake = None if stake.empty else round(float(stake.mean()), 4)
        clv = pd.to_numeric(cleaned.get('clv_percent', pd.Series(dtype=float)), errors='coerce').dropna()
        avg_clv = None if clv.empty else round(float(clv.mean()), 6)
    out = dict(summary)
    out['pending_picks'] = pending
    out['avg_stake_units'] = avg_stake
    out['avg_clv_percent'] = avg_clv
    return out


def public_dashboard_table(frame: pd.DataFrame | list[dict[str, Any]], limit: int = 200) -> pd.DataFrame:
    view = client_view(frame, public_only=True)
    if view.empty:
        return pd.DataFrame()
    sort_cols = [col for col in ['locked_at_utc', 'event_start_utc'] if col in view.columns]
    if sort_cols:
        view = view.sort_values(sort_cols, ascending=False, na_position='last')
    return view.head(limit)


def report_card_markdown(frame: pd.DataFrame | list[dict[str, Any]], *, title: str = 'Proof Dashboard', brand: str = 'Private Analytics') -> str:
    metrics = dashboard_metrics(frame)
    hit_rate = metrics.get('hit_rate')
    roi = metrics.get('roi')
    lines = [
        f'# {title}',
        f'**{brand}**',
        '',
        f"Locked picks: **{metrics['locked_picks']}**",
        f"Resolved: **{metrics['resolved_picks']}**",
        f"Record: **{metrics['wins']}-{metrics['losses']}**",
        f"Hit rate: **{'N/A' if hit_rate is None else f'{hit_rate * 100:.1f}%'}**",
        f"Units: **{metrics['profit_units']}**",
        f"ROI: **{'N/A' if roi is None else f'{roi * 100:.1f}%'}**",
        '',
        '_Research only. No guaranteed outcomes._',
    ]
    return '\n'.join(lines)


def report_card_html(frame: pd.DataFrame | list[dict[str, Any]], *, title: str = 'Proof Dashboard', brand: str = 'Private Analytics') -> str:
    metrics = dashboard_metrics(frame)
    hit_rate = metrics.get('hit_rate')
    roi = metrics.get('roi')
    hit_text = 'N/A' if hit_rate is None else f'{hit_rate * 100:.1f}%'
    roi_text = 'N/A' if roi is None else f'{roi * 100:.1f}%'
    return f"""
<div style="font-family:Arial,sans-serif;border:1px solid #333;border-radius:18px;padding:22px;max-width:720px;background:#10141f;color:#f6f7fb;">
  <div style="font-size:14px;letter-spacing:1px;text-transform:uppercase;color:#9fb3c8;">{brand}</div>
  <div style="font-size:34px;font-weight:800;margin:6px 0 18px;">{title}</div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Record</div><div style="font-size:28px;font-weight:800;">{metrics['wins']}-{metrics['losses']}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Hit Rate</div><div style="font-size:28px;font-weight:800;">{hit_text}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">ROI</div><div style="font-size:28px;font-weight:800;">{roi_text}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Locked</div><div style="font-size:28px;font-weight:800;">{metrics['locked_picks']}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Resolved</div><div style="font-size:28px;font-weight:800;">{metrics['resolved_picks']}</div></div>
    <div style="background:#1b2233;border-radius:14px;padding:14px;"><div style="color:#9fb3c8;font-size:12px;">Units</div><div style="font-size:28px;font-weight:800;">{metrics['profit_units']}</div></div>
  </div>
  <div style="margin-top:16px;color:#9fb3c8;font-size:12px;">Research only. No guaranteed outcomes.</div>
</div>
""".strip()


def daily_locked_report(frame: pd.DataFrame | list[dict[str, Any]], *, language: str = 'English', public_only: bool = True) -> str:
    return daily_report(frame, language=language, public_only=public_only)

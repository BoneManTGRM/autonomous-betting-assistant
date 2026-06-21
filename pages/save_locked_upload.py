from __future__ import annotations

import hashlib
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import filter_locked_proof_rows, load_persistent_ledger, merge_ledgers, normalize_workspace_id, save_persistent_ledger
from autonomous_betting_agent.odds_lock_tools import lock_status, now_utc, parse_datetime_utc, profit_units, proof_hash
from autonomous_betting_agent.pick_hold_store import save_held_rows
from autonomous_betting_agent.row_normalizer import normalize_frame, safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Save Locked Upload', layout='wide')
render_app_sidebar('save_locked_upload', language_key='save_locked_upload_language', selector='radio')


def _clean(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').split())


def _stable_id(row: Mapping[str, Any]) -> str:
    parts = [
        safe_text(row.get('event_id') or row.get('game_id') or row.get('fixture_id')),
        safe_text(row.get('event') or row.get('event_name') or row.get('game') or row.get('match')),
        safe_text(row.get('sport') or row.get('sport_key') or row.get('league')),
        safe_text(row.get('market_type') or row.get('market')),
        safe_text(row.get('line_point') or row.get('line')),
        safe_text(row.get('prediction') or row.get('pick') or row.get('selection')),
        safe_text(row.get('event_start_utc') or row.get('commence_time') or row.get('start')),
    ]
    digest = hashlib.sha256('|'.join(_clean(part) for part in parts).encode('utf-8')).hexdigest()
    return f'LEG-{digest[:12].upper()}'


def repair_legacy_rows(frame: pd.DataFrame, *, workspace_id: str) -> pd.DataFrame:
    normalized = normalize_frame(frame)
    if normalized.empty:
        return pd.DataFrame()
    locked_time = now_utc()
    locked_dt = parse_datetime_utc(locked_time)
    rows = []
    for row in normalized.to_dict('records'):
        item = dict(row)
        item['locked_at_utc'] = safe_text(item.get('locked_at_utc') or item.get('locked_at') or item.get('prediction_timestamp') or item.get('created_at')) or locked_time
        item['test_window_id'] = workspace_id
        item['ledger_type'] = safe_text(item.get('ledger_type')) or 'legacy_uploaded_research_test'
        item['official_ev_pick'] = False
        item['research_lock_ready'] = True
        item['official_lock_ready'] = False
        item['public_confidence'] = safe_text(item.get('public_confidence')) or 'Legacy Uploaded Research/Test'
        item['public_reason'] = safe_text(item.get('public_reason')) or 'Recovered uploaded research/test row after storage reset.'
        item['stake_units'] = item.get('stake_units') or 1.0
        item['proof_status'] = lock_status(item, locked_at=locked_dt)
        item['profit_units'] = profit_units(item)
        item['proof_hash'] = safe_text(item.get('proof_hash')) or proof_hash(item)
        item['proof_id'] = safe_text(item.get('proof_id')) or _stable_id(item)
        rows.append(item)
    return filter_locked_proof_rows(pd.DataFrame(rows))


st.title('Save Locked Upload')
st.caption('Saves an already locked CSV, or repairs a legacy 38-row proof file after storage was cleared.')

workspace_input = st.text_input('Workspace ID', value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

upload = st.file_uploader('Upload proof CSV', type=['csv'])
if upload is None:
    st.info('Upload the 38-row CSV here.')
    st.stop()

raw = pd.read_csv(upload)
locked = filter_locked_proof_rows(raw)
repaired = repair_legacy_rows(raw, workspace_id=workspace_id) if locked.empty else pd.DataFrame()
rows_to_save = locked if not locked.empty else repaired
existing = load_persistent_ledger(workspace_id=workspace_id)
combined = merge_ledgers(existing, rows_to_save)

cols = st.columns(5)
cols[0].metric('Uploaded rows', len(raw))
cols[1].metric('Already locked rows', len(locked))
cols[2].metric('Repaired rows', len(repaired))
cols[3].metric('Existing saved rows', len(existing))
cols[4].metric('After save total', len(combined))

if rows_to_save.empty:
    st.error('No usable rows found. The CSV is missing event/prediction data.')
    st.dataframe(raw, use_container_width=True, hide_index=True)
    st.stop()

st.dataframe(rows_to_save, use_container_width=True, hide_index=True)

if st.button('Save these rows to workspace', type='primary', use_container_width=True):
    saved = save_persistent_ledger(combined, workspace_id=workspace_id)
    records = saved.to_dict('records') if not saved.empty else []
    for key in ['odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows']:
        st.session_state[key] = records
        save_held_rows(key, records, workspace_id)
    st.success(f'Saved: {workspace_id} / {len(saved)} rows')

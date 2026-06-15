from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_users import current_user_from_session, list_user_profiles
from autonomous_betting_agent.proof_ledger import ledger_summary, load_ledger, sport_breakdown, verify_hash_chain

st.set_page_config(page_title='Public Results Dashboard', layout='wide')
st.title('Public Results Dashboard')
st.caption('Read-only performance view for buyers, testers, and subscribers. Uses the local proof ledger; no cloud server required.')

profiles = list_user_profiles()
profile = current_user_from_session(st.session_state)
mode = st.radio('View mode', ['Active user', 'All local users'], horizontal=True)

if mode == 'All local users':
    frames = []
    for item in profiles:
        frame = load_ledger(item.user_id)
        if not frame.empty:
            frame = frame.copy()
            frame['local_user_display_name'] = item.display_name
            frames.append(frame)
    ledger = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    title_suffix = 'All local users'
else:
    ledger = load_ledger(profile.user_id)
    title_suffix = f'{profile.display_name} ({profile.user_id})'

st.subheader(title_suffix)
summary = ledger_summary(ledger)
verification = verify_hash_chain(ledger)

cols = st.columns(8)
cols[0].metric('Total picks', summary['total_picks'])
cols[1].metric('Wins', summary['wins'])
cols[2].metric('Losses', summary['losses'])
cols[3].metric('Win rate', '' if summary['win_rate'] is None else f"{summary['win_rate']:.1%}")
cols[4].metric('Units', f"{summary['units']:.2f}")
cols[5].metric('ROI', '' if summary['roi_percent'] is None else f"{summary['roi_percent']:.2f}%")
cols[6].metric('A+ picks', summary['a_plus'])
cols[7].metric('Avg odds', '' if summary['avg_decimal_price'] is None else summary['avg_decimal_price'])

if verification.valid:
    st.success(f'Proof ledger hash chain valid for {verification.rows_checked} rows.')
else:
    st.error(f'Proof ledger hash chain warning: {verification.message}')

if ledger.empty:
    st.warning('No public results yet. Add rows in the Proof Ledger page.')
    st.stop()

st.subheader('Sport breakdown')
st.dataframe(sport_breakdown(ledger), use_container_width=True, hide_index=True)

st.subheader('Confidence-tier breakdown')
if 'confidence_tier' in ledger.columns:
    rows = []
    for tier, group in ledger.groupby(ledger['confidence_tier'].fillna('Unknown').astype(str)):
        tier_summary = ledger_summary(group)
        rows.append({'confidence_tier': tier, **tier_summary})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info('No confidence_tier column found.')

st.subheader('Recent proof records')
public_cols = [
    'prediction_timestamp',
    'event',
    'sport',
    'prediction',
    'model_probability',
    'decimal_price',
    'decision',
    'confidence_tier',
    'result_status',
    'profit_units',
    'row_hash',
]
st.dataframe(ledger[[col for col in public_cols if col in ledger.columns]].tail(100), use_container_width=True, hide_index=True)

with st.expander('Buyer note', expanded=False):
    st.write('This page is designed to show the record without exposing secrets, code, or private API keys. For a real public launch, add authentication, hosting controls, and a managed database.')

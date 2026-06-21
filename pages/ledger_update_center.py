from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.auto_result_grading_tools import grading_summary
from autonomous_betting_agent.commercial_platform_tools import dashboard_metrics, load_persistent_ledger
from autonomous_betting_agent.dashboard_sync import sync_dashboard_state
from autonomous_betting_agent.result_grading_v2 import apply_fuzzy_updates, normalize_results

st.set_page_config(page_title='Ledger Update Center', layout='wide')
st.title('Ledger Update Center')
st.caption('Apply finished-result rows, save the ledger, and sync the dashboard session in one step.')

ledger = load_persistent_ledger()
st.subheader('Current ledger')
st.json(grading_summary(ledger))
st.json(dashboard_metrics(ledger) if not ledger.empty else {})

upload = st.file_uploader('Upload finished results CSV', type=['csv'])
if upload is not None:
    result_frame = normalize_results(pd.read_csv(upload))
    st.subheader('Result preview')
    st.dataframe(result_frame, use_container_width=True, hide_index=True)
    if st.button('Apply results and sync dashboard', type='primary', use_container_width=True):
        updated, stats = apply_fuzzy_updates(ledger, result_frame)
        st.json(stats)
        if updated.empty:
            st.warning('No rows were updated.')
        else:
            saved = sync_dashboard_state(updated)
            st.success(f'Saved and synced {len(saved)} rows.')
            show_cols = [col for col in ['event', 'prediction', 'result_status', 'winner', 'final_score', 'grading_match_status', 'grading_match_confidence'] if col in saved.columns]
            st.dataframe(saved[show_cols] if show_cols else saved, use_container_width=True, hide_index=True)

if st.button('Sync dashboard from saved ledger', use_container_width=True):
    saved = sync_dashboard_state(ledger)
    if saved.empty:
        st.warning('No saved ledger found.')
    else:
        st.success(f'Synced {len(saved)} rows.')

st.subheader('Ledger preview')
st.dataframe(ledger, use_container_width=True, hide_index=True)

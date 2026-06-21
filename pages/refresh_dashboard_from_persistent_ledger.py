from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar

st.set_page_config(page_title='Refresh Dashboard Ledger', layout='wide')
render_tool_sidebar('refresh_dashboard_from_persistent_ledger', 'English')

st.title('Refresh Dashboard Ledger')
st.caption('Copies the saved persistent proof ledger into the Streamlit session rows used by the Public Proof Dashboard.')

ledger = load_persistent_ledger()
st.metric('Persistent ledger rows', 0 if ledger.empty else len(ledger))

if st.button('Refresh dashboard from saved ledger', type='primary', use_container_width=True):
    if ledger.empty:
        st.error('No saved persistent ledger found.')
    else:
        rows = ledger.to_dict(orient='records')
        st.session_state['odds_lock_pro_locked_rows'] = rows
        st.session_state['public_proof_dashboard_refresh_rows'] = rows
        st.success('Dashboard session refreshed. Open Public Proof Dashboard and refresh the page.')
        show_cols = [col for col in ['event', 'prediction', 'result_status', 'winner', 'final_score', 'graded_at_utc'] if col in ledger.columns]
        st.dataframe(ledger[show_cols] if show_cols else ledger, use_container_width=True, hide_index=True)

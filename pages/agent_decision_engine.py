from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import (
    agent_decision_summary,
    build_agent_decisions,
    lock_ready_candidates,
    playable_candidates,
)

st.set_page_config(page_title='Agent Decision Engine', layout='wide')
st.title('Agent Decision Engine')
st.caption('Evaluates rows and recommends play_strong, play_small, watch_only, no_action, or review_needed using edge, odds, field coverage, line movement, and event timing safety.')

min_edge = st.slider('Minimum model-vs-market edge', min_value=0.0, max_value=0.20, value=0.035, step=0.005)
strong_edge = st.slider('Strong edge threshold', min_value=0.0, max_value=0.30, value=0.075, step=0.005)
upload = st.file_uploader('Upload CSV', type=['csv'])
pasted = st.text_area('Or paste CSV text', height=120)

if upload is not None:
    raw = pd.read_csv(upload)
    source_label = upload.name
elif pasted.strip():
    raw = pd.read_csv(StringIO(pasted.strip()))
    source_label = 'pasted_csv'
else:
    raw = pd.DataFrame()
    source_label = ''

if raw.empty:
    st.warning('Upload or paste a CSV to run agent decisions.')
    st.stop()

decisions = build_agent_decisions(raw, min_edge=float(min_edge), strong_edge=float(strong_edge))
plays = playable_candidates(raw, min_edge=float(min_edge), strong_edge=float(strong_edge))
lock_ready = lock_ready_candidates(raw, min_edge=float(min_edge), strong_edge=float(strong_edge))
summary = agent_decision_summary(raw, min_edge=float(min_edge), strong_edge=float(strong_edge))

st.info(f'Source: {source_label} | Rows: {summary["rows"]} | Min edge: {min_edge:.3f} | Strong edge: {strong_edge:.3f}')
cols = st.columns(9)
cols[0].metric('Strong', summary['play_strong'])
cols[1].metric('Small', summary['play_small'])
cols[2].metric('Watch', summary['watch_only'])
cols[3].metric('No Action', summary['no_action'])
cols[4].metric('Review', summary['review_needed'])
cols[5].metric('Lock Ready', summary['lock_ready_candidates'])
cols[6].metric('Stake Units', summary['recommended_total_stake_units'])
cols[7].metric('Avg Score', 'N/A' if summary['average_score'] is None else summary['average_score'])
cols[8].metric('Rows', summary['rows'])

priority_cols = [
    'event',
    'sport',
    'market_type',
    'prediction',
    'model_probability_clean',
    'market_implied_probability',
    'model_market_edge',
    'model_market_edge_percent',
    'decimal_price',
    'agent_decision',
    'agent_score',
    'recommended_stake_units',
    'event_timing_status',
    'lock_ready',
    'already_locked',
    'field_coverage_score',
    'line_value_signal',
    'decision_reasons',
    'decision_signals',
]
view_cols = [col for col in priority_cols if col in decisions.columns]

tab_all, tab_plays, tab_lock_ready = st.tabs(['All Decisions', 'Playable Candidates', 'Lock-Ready Candidates'])
with tab_all:
    st.dataframe(decisions[view_cols].head(500) if view_cols else decisions.head(500), use_container_width=True, hide_index=True)
with tab_plays:
    st.dataframe(plays[view_cols].head(500) if not plays.empty and view_cols else plays.head(500), use_container_width=True, hide_index=True)
with tab_lock_ready:
    st.dataframe(lock_ready[view_cols].head(500) if not lock_ready.empty and view_cols else lock_ready.head(500), use_container_width=True, hide_index=True)

st.download_button('Download all agent decisions CSV', decisions.to_csv(index=False), file_name='agent_decisions.csv', mime='text/csv')
st.download_button('Download playable candidates CSV', plays.to_csv(index=False), file_name='agent_playable_candidates.csv', mime='text/csv')
st.download_button('Download lock-ready candidates CSV', lock_ready.to_csv(index=False), file_name='agent_lock_ready_candidates.csv', mime='text/csv')

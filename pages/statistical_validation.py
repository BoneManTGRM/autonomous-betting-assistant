from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.proof_ledger import load_ledger
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.stat_validation import roi_scenarios, statistical_summary

st.set_page_config(page_title='Statistical Validation', layout='wide')
st.title('Statistical Validation')
st.caption('Shows sample-size risk, Wilson confidence interval, break-even odds, and ROI scenarios. This keeps small samples from being overstated.')

profile = current_user_from_session(st.session_state)
source = st.radio('Data source', ['Proof ledger', 'Upload CSV'], horizontal=True)

if source == 'Proof ledger':
    frame = load_ledger(profile.user_id)
    source_label = 'Proof ledger'
else:
    upload = st.file_uploader('Upload graded CSV', type=['csv'])
    pasted = st.text_area('Or paste CSV text', height=120)
    if upload is not None:
        frame = pd.read_csv(upload)
        source_label = upload.name
    elif pasted.strip():
        frame = pd.read_csv(StringIO(pasted.strip()))
        source_label = 'pasted_csv'
    else:
        frame = pd.DataFrame()
        source_label = ''

if frame.empty:
    st.warning('No rows found. Upload graded rows or add proof-ledger data first.')
    st.stop()

normalized = normalize_frame(frame)
summary = statistical_summary(normalized)

st.info(f'Source: {source_label}')
cols = st.columns(6)
cols[0].metric('Wins', summary['wins'])
cols[1].metric('Losses', summary['losses'])
cols[2].metric('Resolved', summary['total'])
cols[3].metric('Observed Win Rate', '' if summary['observed_win_rate'] is None else f"{summary['observed_win_rate']:.1%}")
cols[4].metric('95% Low', '' if summary['wilson_low_95'] is None else f"{summary['wilson_low_95']:.1%}")
cols[5].metric('95% High', '' if summary['wilson_high_95'] is None else f"{summary['wilson_high_95']:.1%}")

st.warning(summary['sample_warning'])

st.subheader('Break-even odds at observed hit rate')
be_cols = st.columns(2)
be_cols[0].metric('Break-even decimal', summary['break_even_decimal_at_observed_rate'] or 'N/A')
be_cols[1].metric('Break-even American', summary['break_even_american_at_observed_rate'] or 'N/A')

st.subheader('ROI scenarios')
st.caption('Observed rate is the current result. Wilson low/high show uncertainty from sample size. Use the low case when being conservative.')
st.dataframe(roi_scenarios(summary['wins'], summary['losses']), use_container_width=True, hide_index=True)

st.subheader('Normalized rows used')
st.dataframe(normalized.head(100), use_container_width=True, hide_index=True)

st.download_button('Download normalized statistical input CSV', normalized.to_csv(index=False), file_name='statistical_validation_input.csv', mime='text/csv')
st.download_button('Download ROI scenarios CSV', roi_scenarios(summary['wins'], summary['losses']).to_csv(index=False), file_name='roi_scenarios.csv', mime='text/csv')

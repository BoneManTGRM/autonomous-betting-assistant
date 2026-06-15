from __future__ import annotations

from io import StringIO
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from autonomous_betting_agent.daily_report import build_daily_report, daily_report_markdown, filter_report_date
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Daily Operations Report', layout='wide')
st.title('Daily Operations Report')
st.caption('Summarizes daily rows, grading status, quality warnings, units, line movement, and recommendations.')

report_date = st.date_input('Report date', value=datetime.now(timezone.utc).date())
starting_units = st.number_input('Starting units', min_value=1.0, max_value=100000.0, value=100.0, step=10.0)
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
    st.warning('Upload or paste a CSV to build the daily report.')
    st.stop()

normalized = normalize_frame(raw)
report = build_daily_report(normalized, report_date=report_date.isoformat(), starting_units=float(starting_units))
markdown = daily_report_markdown(report)
daily_rows = filter_report_date(normalized, report_date.isoformat())

st.info(f'Source: {source_label} | Report date: {report["report_date"]} | Rows reviewed: {report["rows_reviewed"]}')
cols = st.columns(6)
cols[0].metric('Quality Score', f'{report["quality_score"]}/100')
cols[1].metric('Wins', report['statistics']['wins'])
cols[2].metric('Losses', report['statistics']['losses'])
cols[3].metric('Pending', report['grading']['pending'])
cols[4].metric('Review Needed', report['grading']['review_needed'])
cols[5].metric('Net Units', report['bankroll']['net_units'])

st.subheader('Report preview')
st.markdown(markdown)

st.subheader('Rows matched to date')
st.dataframe(daily_rows.head(300) if not daily_rows.empty else normalized.head(300), use_container_width=True, hide_index=True)

with st.expander('Raw daily report JSON', expanded=False):
    st.json(report)

st.download_button('Download daily report Markdown', markdown, file_name='daily_operations_report.md', mime='text/markdown')
st.download_button('Download daily report JSON', json.dumps(report, indent=2, default=str), file_name='daily_operations_report.json', mime='application/json')
st.download_button('Download matched rows CSV', (daily_rows if not daily_rows.empty else normalized).to_csv(index=False), file_name='daily_operations_rows.csv', mime='text/csv')

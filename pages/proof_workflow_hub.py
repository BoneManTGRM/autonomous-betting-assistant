from __future__ import annotations

from io import StringIO
import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.data_intake_gate import gates_frame, intake_gate, recognized_counts_frame
from autonomous_betting_agent.row_normalizer import normalize_frame

WORKFLOW_STEPS = [
    {
        'step': 1,
        'page': 'Export Templates',
        'purpose': 'Create future CSVs with the correct columns.',
        'when_to_use': 'Before generating new prediction exports.',
    },
    {
        'step': 2,
        'page': 'Data Intake Gate',
        'purpose': 'Check whether a CSV is ready for learning, stats, proof, ROI, CLV, or forward testing.',
        'when_to_use': 'First stop for every new CSV.',
    },
    {
        'step': 3,
        'page': 'CSV Doctor',
        'purpose': 'Diagnose exact column mapping and missing fields.',
        'when_to_use': 'When a CSV does not behave as expected.',
    },
    {
        'step': 4,
        'page': 'Odds Lock',
        'purpose': 'Create a timestamped lock for new predictions before events start.',
        'when_to_use': 'Only before games/events start.',
    },
    {
        'step': 5,
        'page': 'Statistical Validation',
        'purpose': 'Measure sample size, observed hit rate, confidence interval, and ROI scenarios.',
        'when_to_use': 'After rows have clean win/loss results.',
    },
    {
        'step': 6,
        'page': 'Proof Readiness',
        'purpose': 'Separate official proof from historical learning/backfill rows.',
        'when_to_use': 'Before showing results to a buyer or serious user.',
    },
    {
        'step': 7,
        'page': 'Forward Test Tracker',
        'purpose': 'Track progress toward 25, 100, 500, and 1,000 locked rows.',
        'when_to_use': 'During live forward testing.',
    },
    {
        'step': 8,
        'page': 'Live Command Center',
        'purpose': 'See current status, warnings, quality, stake sizing, locks, and ledger metrics together.',
        'when_to_use': 'Daily operational view.',
    },
    {
        'step': 9,
        'page': 'Executive Demo Mode',
        'purpose': 'Show a cleaner buyer/investor demo view.',
        'when_to_use': 'After proof rows and reports are ready.',
    },
]

st.set_page_config(page_title='Proof Workflow Hub', layout='wide')
st.title('Proof Workflow Hub')
st.caption('A guided workflow for turning raw prediction exports into clean learning, proof, statistics, and buyer-ready reports.')

st.subheader('Recommended workflow')
st.dataframe(pd.DataFrame(WORKFLOW_STEPS), use_container_width=True, hide_index=True)

upload = st.file_uploader('Optional: upload a CSV to get a page recommendation', type=['csv'])
pasted = st.text_area('Or paste CSV text', height=120)

raw = pd.DataFrame()
source_label = ''
if upload is not None:
    raw = pd.read_csv(upload)
    source_label = upload.name
elif pasted.strip():
    raw = pd.read_csv(StringIO(pasted.strip()))
    source_label = 'pasted_csv'

if raw.empty:
    st.info('Upload a CSV here if you want the hub to recommend the next page.')
    st.stop()

normalized = normalize_frame(raw)
report = intake_gate(raw)
ready_gates = [gate['gate'] for gate in report.get('gates', []) if gate.get('ready')]
blocked_gates = [gate['gate'] for gate in report.get('gates', []) if not gate.get('ready')]

st.info(f'Source: {source_label} | Status: {report["overall_status"].upper()} | {report["summary"]}')
cols = st.columns(5)
cols[0].metric('Rows', report['rows'])
cols[1].metric('Ready gates', len(ready_gates))
cols[2].metric('Blocked gates', len(blocked_gates))
cols[3].metric('Proof score', f"{report['proof_summary']['proof_score']}/100")
cols[4].metric('Resolved rows', report['statistical_summary']['total'])

st.subheader('Recommended next page')
if report['blockers']:
    st.error('Go to CSV Doctor first. The file has blockers that should be fixed before using the rest of the app.')
elif 'Odds lock readiness' in ready_gates and 'Official proof readiness' not in ready_gates:
    st.success('Go to Odds Lock if these are current pre-event predictions. Do not use Odds Lock for historical rows.')
elif 'Statistical validation' in ready_gates and 'Official proof readiness' not in ready_gates:
    st.success('Go to Statistical Validation and Proof Readiness. This file has results, but not official forward locks.')
elif 'Official proof readiness' in ready_gates:
    st.success('Go to Forward Test Tracker and Live Command Center. Official locked rows were detected.')
else:
    st.warning('Go to Data Intake Gate or CSV Doctor. The file is limited and needs more required fields.')

if report['warnings']:
    st.subheader('Warnings')
    for item in report['warnings']:
        st.warning(item)

if report['next_actions']:
    st.subheader('Next actions')
    for item in report['next_actions']:
        st.write(f'- {item}')

st.subheader('Readiness gates')
st.dataframe(gates_frame(report), use_container_width=True, hide_index=True)

st.subheader('Recognized fields')
st.dataframe(recognized_counts_frame(report), use_container_width=True, hide_index=True)

with st.expander('Normalized preview', expanded=False):
    st.dataframe(normalized.head(100), use_container_width=True, hide_index=True)

st.download_button('Download workflow intake report JSON', json.dumps(report, indent=2, default=str), file_name='workflow_intake_report.json', mime='application/json')

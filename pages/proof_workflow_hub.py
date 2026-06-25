from __future__ import annotations

from io import StringIO
import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.data_intake_gate import gates_frame, intake_gate, recognized_counts_frame
from autonomous_betting_agent.row_normalizer import normalize_frame

WORKFLOW_STEPS = [
    {'step': 1, 'page': 'Export Templates', 'purpose': 'Create future CSVs with the correct columns.', 'when_to_use': 'Before generating new prediction exports.'},
    {'step': 2, 'page': 'Scanner Pro', 'purpose': 'One consolidated live scanner for all supported sports, leagues, books, and markets.', 'when_to_use': 'When you want fresh live odds/market discovery.'},
    {'step': 3, 'page': 'Pro Predictor', 'purpose': 'Main all-sports prediction engine. This replaces separate single-sport predictors such as NBA-only pages.', 'when_to_use': 'When you want final scored predictions.'},
    {'step': 4, 'page': 'What Are the Odds', 'purpose': 'One consolidated market/value finder for scanner rows, predictor rows, odds exports, props, CLV, losses, walk-forward checks, and segments.', 'when_to_use': 'When you want to find playable value or lock-ready candidates.'},
    {'step': 5, 'page': 'Data Intake Gate', 'purpose': 'Check whether a CSV is ready for learning, statistics, proof, ROI, line movement, or tracking.', 'when_to_use': 'First stop for any outside CSV.'},
    {'step': 6, 'page': 'CSV Doctor', 'purpose': 'Diagnose exact column mapping and missing fields.', 'when_to_use': 'When a CSV does not behave as expected.'},
    {'step': 7, 'page': 'Quality Control Center', 'purpose': 'Check duplicates, conflicts, grading, line movement, bankroll path, and version coverage.', 'when_to_use': 'Before trusting or presenting a dataset.'},
    {'step': 8, 'page': 'Assistant Decision Engine', 'purpose': 'Recommend play_strong, play_small, watch_only, no_action, or review_needed from edge, odds, coverage, timing, and line movement.', 'when_to_use': 'Before locking new candidate rows.'},
    {'step': 9, 'page': 'Odds Lock', 'purpose': 'Create a timestamped lock for new predictions before events start.', 'when_to_use': 'Only before games/events start.'},
    {'step': 10, 'page': 'Learning Memory', 'purpose': 'The only training page. Save durable learned_state, cumulative memory, and ARA memory patterns.', 'when_to_use': 'After results are graded and before judging what the model learned.'},
    {'step': 11, 'page': 'Max Assistant Intelligence', 'purpose': 'Run API snapshot memory, loss autopsy, CLV intelligence, walk-forward validation, and sport-specific routing together.', 'when_to_use': 'After candidate decisions or after importing resolved results.'},
    {'step': 12, 'page': 'Statistical Validation', 'purpose': 'Measure sample size, observed hit rate, confidence interval, and ROI scenarios.', 'when_to_use': 'After rows have clean win/loss results.'},
    {'step': 13, 'page': 'Proof Readiness', 'purpose': 'Separate official proof from historical learning/backfill rows.', 'when_to_use': 'Before showing results to a serious reviewer.'},
    {'step': 14, 'page': 'Forward Test Tracker', 'purpose': 'Track progress toward 25, 100, 500, and 1,000 locked rows.', 'when_to_use': 'During live forward testing.'},
    {'step': 15, 'page': 'Performance Segments', 'purpose': 'Find strengths and weak spots by sport, market, source, probability bucket, odds bucket, and version.', 'when_to_use': 'After enough resolved rows exist.'},
    {'step': 16, 'page': 'Daily Operations Report', 'purpose': 'Create daily status reports with results, units, quality warnings, and recommendations.', 'when_to_use': 'Daily operating review.'},
    {'step': 17, 'page': 'Review Bundle Export', 'purpose': 'Export combined Markdown, JSON, and normalized CSV for serious review.', 'when_to_use': 'When preparing a clean review package.'},
    {'step': 18, 'page': 'Readiness Scorecard', 'purpose': 'Score whether the current data is ready for serious review.', 'when_to_use': 'Before making valuation or performance claims.'},
    {'step': 19, 'page': 'Live Command Center', 'purpose': 'See current status, warnings, quality, stake sizing, locks, and ledger metrics together.', 'when_to_use': 'Daily operational view.'},
    {'step': 20, 'page': 'Demo Data Mode', 'purpose': 'Show the workflow with safe sample data.', 'when_to_use': 'When demonstrating the app without private files.'},
    {'step': 21, 'page': 'Executive Demo Mode', 'purpose': 'Show a cleaner demo view after proof rows and reports are ready.', 'when_to_use': 'Final presentation view.'},
]

st.set_page_config(page_title='Proof Workflow Hub', layout='wide')
st.title('Proof Workflow Hub')
st.caption('A guided workflow for turning raw prediction exports into clean scanning, prediction, market finding, learning, proof, intelligence, reports, and review-ready packages.')

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
    st.success('Go to What Are the Odds, Quality Control Center, Assistant Decision Engine, Odds Lock, Learning Memory, then Max Assistant Intelligence.')
elif 'Statistical validation' in ready_gates and 'Official proof readiness' not in ready_gates:
    st.success('Go to Learning Memory, Max Assistant Intelligence, Statistical Validation, Proof Readiness, and Readiness Scorecard.')
elif 'Official proof readiness' in ready_gates:
    st.success('Go to Learning Memory, Max Assistant Intelligence, Forward Test Tracker, Daily Operations Report, Review Bundle Export, and Live Command Center.')
else:
    st.warning('Go to Scanner Pro or Pro Predictor for fresh rows. For outside CSVs, use Data Intake Gate or CSV Doctor.')

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

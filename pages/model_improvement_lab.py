from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from autonomous_betting_agent.model_lab import lab_summary, recommendations_from_patterns

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'

st.set_page_config(page_title='Model Improvement Lab', layout='wide')
st.title('Model Improvement Lab')
st.caption('Turns learned memory patterns into simple actions: raise trust, lower trust, watch, stable, or ignore until more data.')

try:
    bank = json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8')) if MEMORY_BANK_PATH.exists() else {}
except Exception as exc:
    st.error(f'Could not read learning memory bank: {exc}')
    bank = {}

patterns = bank.get('patterns', []) if isinstance(bank, dict) else []
recommendations = recommendations_from_patterns(patterns)
summary = lab_summary(recommendations)

cols = st.columns(5)
cols[0].metric('Raise trust', summary['raise_trust'])
cols[1].metric('Lower trust', summary['lower_trust'])
cols[2].metric('Watch', summary['watch'])
cols[3].metric('Stable', summary['stable'])
cols[4].metric('Needs more data', summary['ignore_until_more_data'])

if recommendations.empty:
    st.warning('No learning patterns found yet. Train Learning Memory first.')
else:
    priority = st.multiselect('Priority filter', sorted(recommendations['priority'].dropna().unique()), default=list(sorted(recommendations['priority'].dropna().unique())))
    filtered = recommendations[recommendations['priority'].isin(priority)] if priority else recommendations
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button('Download improvement recommendations CSV', filtered.to_csv(index=False), file_name='model_improvement_recommendations.csv', mime='text/csv')

with st.expander('How to interpret this', expanded=False):
    st.write('Raise trust means the pattern outperformed its predicted probability. Lower trust means it underperformed. Watch means it moved enough to monitor but not enough for a strong rule. More data is needed before making aggressive model changes.')

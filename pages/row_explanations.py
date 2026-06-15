from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.pick_explainer import build_pick_explanations

st.set_page_config(page_title='Row Explanations', layout='wide')
st.title('Row Explanations')
st.caption('Summarizes the main fields behind each row and highlights missing information.')

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
    st.warning('Upload or paste a CSV to inspect row explanations.')
    st.stop()

explained = build_pick_explanations(raw)

st.info(f'Source: {source_label} | Rows: {len(explained)}')
cols = st.columns(4)
cols[0].metric('Rows', len(explained))
cols[1].metric('Avg Signal Count', round(float(explained['positive_signal_count'].mean()), 2) if not explained.empty else 0)
cols[2].metric('Avg Missing/Warning Count', round(float(explained['risk_flag_count'].mean()), 2) if not explained.empty else 0)
cols[3].metric('Rows With Warnings', int((explained['risk_flag_count'] > 0).sum()) if not explained.empty else 0)

view_cols = [col for col in ['event', 'prediction', 'model_probability', 'decimal_price', 'confidence_tier', 'explanation_summary', 'positive_signal_count', 'risk_flag_count', 'positive_signals', 'risk_flags'] if col in explained.columns]
st.dataframe(explained[view_cols].head(300) if view_cols else explained.head(300), use_container_width=True, hide_index=True)

st.download_button('Download row explanations CSV', explained.to_csv(index=False), file_name='row_explanations.csv', mime='text/csv')

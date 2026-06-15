from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.performance_segments import build_segment_frame, top_segments

st.set_page_config(page_title='Performance Segments', layout='wide')
st.title('Performance Segments')
st.caption('Breaks performance down by sport, market, confidence, probability bucket, odds bucket, source, book, and model version.')

upload = st.file_uploader('Upload CSV', type=['csv'])
pasted = st.text_area('Or paste CSV text', height=120)
min_resolved = st.number_input('Minimum resolved rows for top segment view', min_value=1, max_value=1000, value=3, step=1)

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
    st.warning('Upload or paste a CSV to analyze performance segments.')
    st.stop()

segments = build_segment_frame(raw)
top = top_segments(raw, min_resolved=int(min_resolved))

st.info(f'Source: {source_label} | Segment rows: {len(segments)}')

st.subheader('Top segments')
st.dataframe(top, use_container_width=True, hide_index=True)

st.subheader('All segments')
st.dataframe(segments, use_container_width=True, hide_index=True)

st.download_button('Download all performance segments CSV', segments.to_csv(index=False), file_name='performance_segments.csv', mime='text/csv')
st.download_button('Download top performance segments CSV', top.to_csv(index=False), file_name='top_performance_segments.csv', mime='text/csv')

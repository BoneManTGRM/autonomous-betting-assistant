from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.result_grader import grade_frame, grade_summary

st.set_page_config(page_title='Auto Result Grader', layout='wide')
st.title('Auto Result Grader')
st.caption('Grades rows from existing result fields or by comparing prediction to winner. Rows with unclear data are marked for review.')

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
    st.warning('Upload or paste a CSV to grade results.')
    st.stop()

graded = grade_frame(raw)
summary = grade_summary(raw)

st.info(f'Source: {source_label} | Rows: {summary["rows"]}')
cols = st.columns(6)
cols[0].metric('Wins', summary['wins'])
cols[1].metric('Losses', summary['losses'])
cols[2].metric('Voids', summary['voids'])
cols[3].metric('Pending', summary['pending'])
cols[4].metric('Review needed', summary['review_needed'])
cols[5].metric('Rows', summary['rows'])

review = graded[graded['needs_review'].astype(bool)].copy() if 'needs_review' in graded.columns else pd.DataFrame()
if review.empty:
    st.success('No manual review rows detected.')
else:
    st.warning(f'{len(review)} rows need manual review.')

st.subheader('Review needed')
st.dataframe(review.head(300), use_container_width=True, hide_index=True)
st.subheader('Graded rows')
st.dataframe(graded.head(300), use_container_width=True, hide_index=True)

st.download_button('Download graded CSV', graded.to_csv(index=False), file_name='auto_graded_results.csv', mime='text/csv')
if not review.empty:
    st.download_button('Download review rows CSV', review.to_csv(index=False), file_name='auto_grade_review_rows.csv', mime='text/csv')

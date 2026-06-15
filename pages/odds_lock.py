from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots, snapshot_summary, verify_snapshots

st.set_page_config(page_title='Odds Lock', layout='wide')
st.title('Odds Lock / Prediction Snapshot')
st.caption('Locks model probability, odds, bookmaker/source, timestamp, EV, and decision into a tamper-evident snapshot before results are graded.')

profile = current_user_from_session(st.session_state)
st.info(f'Active local user: {profile.display_name} ({profile.user_id})')

upload = st.file_uploader('Upload prediction CSV to lock', type=['csv'])
pasted = st.text_area('Or paste prediction CSV text', height=120)
frame = pd.DataFrame()
if upload is not None:
    frame = pd.read_csv(upload)
elif pasted.strip():
    frame = pd.read_csv(StringIO(pasted.strip()))

if frame.empty:
    st.warning('Upload predictions to create an odds-locked snapshot.')
    st.stop()

snapshots = build_prediction_snapshots(frame, user_id=profile.user_id)
summary = snapshot_summary(snapshots)
verification = verify_snapshots(snapshots)

cols = st.columns(5)
cols[0].metric('Rows', summary['total'])
cols[1].metric('Official locked', summary['official_locked'])
cols[2].metric('Not official', summary['not_official'])
cols[3].metric('Missing odds', summary['missing_odds'])
cols[4].metric('Missing probability', summary['missing_probability'])

if verification.valid:
    st.success(f'Snapshot hashes valid for {verification.rows_checked} rows.')
else:
    st.error(f'Snapshot hash problem: {verification.message}')

st.subheader('Snapshot records')
st.dataframe(snapshots, use_container_width=True, hide_index=True)
st.download_button('Download locked snapshot CSV', snapshots.to_csv(index=False), file_name=f'{profile.user_id}_prediction_snapshots.csv', mime='text/csv')

with st.expander('Official-pick rule', expanded=False):
    st.write('A row is official only if it has event, prediction, model_probability, decimal_price, and a lock timestamp. Missing odds/probability rows can still be reviewed, but should not be counted as official ROI proof.')

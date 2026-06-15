from __future__ import annotations

from io import StringIO
import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.api_snapshot_memory import build_api_snapshots, export_snapshot_manifest, snapshot_memory_summary
from autonomous_betting_agent.clv_intelligence import build_clv_intelligence, clv_by_segment, clv_summary
from autonomous_betting_agent.post_loss_autopsy import autopsy_summary, build_loss_autopsies, future_rules
from autonomous_betting_agent.sport_specific_models import build_sport_specific_decisions, sport_model_summary
from autonomous_betting_agent.walk_forward_lab import walk_forward_summary, walk_forward_validate

st.set_page_config(page_title='Max Agent Intelligence', layout='wide')
st.title('Max Agent Intelligence')
st.caption('Runs the highest-value intelligence layers together: API snapshot memory, loss autopsy, CLV intelligence, walk-forward validation, and sport-specific routing.')

upload = st.file_uploader('Upload CSV', type=['csv'])
pasted = st.text_area('Or paste CSV text', height=120)
min_train_rows = st.number_input('Walk-forward minimum training rows', min_value=1, max_value=500, value=10, step=1)

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
    st.warning('Upload or paste a CSV to run the max intelligence stack.')
    st.stop()

snapshots = build_api_snapshots(raw)
snapshot_summary = snapshot_memory_summary(raw)
manifest = export_snapshot_manifest(raw)
losses = build_loss_autopsies(raw)
loss_summary = autopsy_summary(raw)
rules = future_rules(raw)
clv = build_clv_intelligence(raw)
clv_stats = clv_summary(raw)
clv_sport = clv_by_segment(raw, 'sport')
walk = walk_forward_validate(raw, min_train_rows=int(min_train_rows))
walk_stats = walk_forward_summary(raw, min_train_rows=int(min_train_rows))
sport_decisions = build_sport_specific_decisions(raw)
sport_summary = sport_model_summary(raw)

st.info(f'Source: {source_label} | Rows: {len(raw)}')
cols = st.columns(8)
cols[0].metric('Snapshots', snapshot_summary['rows'])
cols[1].metric('Core Coverage', snapshot_summary['avg_core_coverage'])
cols[2].metric('Losses Reviewed', loss_summary['losses_reviewed'])
cols[3].metric('CLV Ready', clv_stats['ready'])
cols[4].metric('Beat Close Rate', 'N/A' if clv_stats['beat_close_rate'] is None else f"{clv_stats['beat_close_rate']:.1%}")
cols[5].metric('WF Tested', walk_stats['tested_rows'])
cols[6].metric('WF Brier', 'N/A' if walk_stats['avg_brier_walk_forward'] is None else walk_stats['avg_brier_walk_forward'])
cols[7].metric('Sport Rows', len(sport_decisions))

tab_snapshot, tab_loss, tab_clv, tab_walk, tab_sport, tab_exports = st.tabs([
    'API Snapshot Memory',
    'Post-Loss Autopsy',
    'CLV Intelligence',
    'Walk-Forward Lab',
    'Sport-Specific Models',
    'Exports',
])

with tab_snapshot:
    st.subheader('API Snapshot Memory')
    st.json(snapshot_summary)
    st.dataframe(snapshots.head(300), use_container_width=True, hide_index=True)

with tab_loss:
    st.subheader('Post-Loss Autopsy')
    st.json(loss_summary)
    st.dataframe(losses.head(300), use_container_width=True, hide_index=True)
    st.subheader('Future Rules')
    st.dataframe(rules, use_container_width=True, hide_index=True)

with tab_clv:
    st.subheader('Closing-Line Value Intelligence')
    st.json(clv_stats)
    st.dataframe(clv.head(300), use_container_width=True, hide_index=True)
    st.subheader('CLV by Sport')
    st.dataframe(clv_sport, use_container_width=True, hide_index=True)

with tab_walk:
    st.subheader('Walk-Forward Validation')
    st.json(walk_stats)
    st.dataframe(walk.head(300), use_container_width=True, hide_index=True)

with tab_sport:
    st.subheader('Sport-Specific Decision Routing')
    st.dataframe(sport_summary, use_container_width=True, hide_index=True)
    st.dataframe(sport_decisions.head(300), use_container_width=True, hide_index=True)

with tab_exports:
    st.download_button('Download API snapshots CSV', snapshots.to_csv(index=False), file_name='api_snapshot_memory.csv', mime='text/csv')
    st.download_button('Download snapshot manifest JSON', json.dumps(manifest, indent=2, default=str), file_name='api_snapshot_manifest.json', mime='application/json')
    st.download_button('Download loss autopsies CSV', losses.to_csv(index=False), file_name='post_loss_autopsies.csv', mime='text/csv')
    st.download_button('Download future rules CSV', rules.to_csv(index=False), file_name='future_loss_rules.csv', mime='text/csv')
    st.download_button('Download CLV intelligence CSV', clv.to_csv(index=False), file_name='clv_intelligence.csv', mime='text/csv')
    st.download_button('Download walk-forward validation CSV', walk.to_csv(index=False), file_name='walk_forward_validation.csv', mime='text/csv')
    st.download_button('Download sport decisions CSV', sport_decisions.to_csv(index=False), file_name='sport_specific_decisions.csv', mime='text/csv')

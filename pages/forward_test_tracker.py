from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots
from autonomous_betting_agent.proof_ledger import load_ledger
from autonomous_betting_agent.proof_readiness import build_proof_readiness_frame, proof_readiness_summary
from autonomous_betting_agent.stat_validation import statistical_summary

STAGES = [
    {'stage': 'Smoke test', 'target': 25, 'meaning': 'Confirms the proof pipeline works.'},
    {'stage': 'Early proof', 'target': 100, 'meaning': 'First meaningful forward-test sample.'},
    {'stage': 'Serious proof', 'target': 500, 'meaning': 'Stronger buyer conversation.'},
    {'stage': 'Strong proof', 'target': 1000, 'meaning': 'More credible valuation case.'},
]

st.set_page_config(page_title='Forward Test Tracker', layout='wide')
st.title('Forward Test Tracker')
st.caption('Tracks progress toward a serious forward-locked proof sample. Only official forward-proof rows count toward the stage targets.')

profile = current_user_from_session(st.session_state)
ledger = load_ledger(profile.user_id)
snapshots = build_prediction_snapshots(ledger, user_id=profile.user_id) if not ledger.empty else pd.DataFrame()
proof = build_proof_readiness_frame(snapshots)
summary = proof_readiness_summary(snapshots)
stats = statistical_summary(proof)

official = int(summary['official_forward_proof'])
cols = st.columns(5)
cols[0].metric('Official Forward Proof', official)
cols[1].metric('Wins', stats['wins'])
cols[2].metric('Losses', stats['losses'])
cols[3].metric('Observed Win Rate', '' if stats['observed_win_rate'] is None else f"{stats['observed_win_rate']:.1%}")
cols[4].metric('95% Low', '' if stats['wilson_low_95'] is None else f"{stats['wilson_low_95']:.1%}")

stage_rows = []
for item in STAGES:
    target = int(item['target'])
    progress = min(1.0, official / target) if target else 0.0
    stage_rows.append({
        'stage': item['stage'],
        'target_locked_picks': target,
        'current_locked_picks': official,
        'remaining': max(0, target - official),
        'progress_percent': round(progress * 100, 2),
        'status': 'complete' if official >= target else 'in_progress',
        'meaning': item['meaning'],
    })

st.subheader('Forward-test stages')
st.dataframe(pd.DataFrame(stage_rows), use_container_width=True, hide_index=True)
for row in stage_rows:
    st.progress(int(row['progress_percent']), text=f"{row['stage']}: {row['current_locked_picks']} / {row['target_locked_picks']} locked picks")

st.subheader('Rules')
st.write([
    'Only official locked rows count toward this tracker.',
    'Historical fallback rows do not count toward forward proof.',
    'Rows missing odds or model_probability do not count.',
    'Review-needed rows should not be presented as official until fixed.',
    'Use ROI, units, and CLV once odds are consistently captured.',
])

if not proof.empty:
    st.subheader('Official-proof rows')
    st.dataframe(proof[proof['evidence_level'].eq('official_forward_proof')].head(200), use_container_width=True, hide_index=True)
    st.download_button('Download forward proof rows CSV', proof[proof['evidence_level'].eq('official_forward_proof')].to_csv(index=False), file_name=f'{profile.user_id}_forward_proof_rows.csv', mime='text/csv')

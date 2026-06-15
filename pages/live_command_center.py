from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bet_sizing import bet_sizing_summary, build_bet_sizing_frame
from autonomous_betting_agent.data_health import data_health_frame, data_health_score
from autonomous_betting_agent.freshness import build_freshness_frame, freshness_score, freshness_summary
from autonomous_betting_agent.grading_review import build_review_queue, review_summary
from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.pick_quality import build_pick_quality_frame, pick_quality_summary
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots, snapshot_summary
from autonomous_betting_agent.proof_ledger import ledger_summary, load_ledger, verify_hash_chain

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'

st.set_page_config(page_title='Live Command Center', layout='wide')
st.title('Live Command Center')
st.caption('One dashboard for today’s picks, proof status, data health, learning memory, review queue, CLV readiness, and system warnings.')

profile = current_user_from_session(st.session_state)
ledger = load_ledger(profile.user_id)
try:
    memory_bank = json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8')) if MEMORY_BANK_PATH.exists() else {}
except Exception:
    memory_bank = {}
patterns = memory_bank.get('patterns', []) if isinstance(memory_bank, dict) else []

upload = st.file_uploader('Optional: upload today’s prediction CSV', type=['csv'])
if upload is not None:
    active = pd.read_csv(upload)
    source_label = upload.name
elif not ledger.empty:
    active = ledger.copy()
    source_label = 'Proof ledger'
else:
    active = pd.DataFrame()
    source_label = 'No active data'

st.info(f'Active local user: {profile.display_name} ({profile.user_id}) | Source: {source_label}')

if active.empty:
    st.warning('No active prediction data found. Upload a CSV or add proof-ledger rows first.')
    st.stop()

quality = build_pick_quality_frame(active, patterns)
sizing = build_bet_sizing_frame(quality, score_quality=False)
snapshots = build_prediction_snapshots(active, user_id=profile.user_id)
review_queue = build_review_queue(active)
freshness = build_freshness_frame(active, memory_bank=memory_bank)
health = data_health_score(active)
ledger_stats = ledger_summary(ledger)
lock_stats = snapshot_summary(snapshots)
quality_stats = pick_quality_summary(quality)
sizing_stats = bet_sizing_summary(quality)
fresh_stats = freshness_summary(freshness)
review_stats = review_summary(review_queue)
verification = verify_hash_chain(ledger)

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric('Data Health', f"{health['score']:.0f}/100")
m2.metric('Freshness', f'{freshness_score(freshness)}/100')
m3.metric('Elite/Strong Picks', quality_stats['elite'] + quality_stats['strong'])
m4.metric('Official Locked', lock_stats['official_locked'])
m5.metric('Suggested Units', sizing_stats['total_units'])
m6.metric('Ledger Win Rate', '' if ledger_stats['win_rate'] is None else f"{ledger_stats['win_rate']:.1%}")

warnings: list[str] = []
if lock_stats['not_official']:
    warnings.append(f"{lock_stats['not_official']} rows are not official locked.")
if fresh_stats['stale'] or fresh_stats['missing']:
    warnings.append(f"Freshness warnings: {fresh_stats['stale']} stale, {fresh_stats['missing']} missing timestamps.")
if not verification.valid:
    warnings.append('Proof-ledger hash chain has a verification warning.')
if health['score'] < 70:
    warnings.append(f"Data health is {health['grade']}.")
if warnings:
    for warning in warnings:
        st.warning(warning)
else:
    st.success('No major command-center warnings detected.')

tab_quality, tab_stakes, tab_review, tab_health, tab_fresh, tab_ledger = st.tabs(['Best Picks', 'Smart Stakes', 'Review Queue', 'Data Health', 'Freshness', 'Ledger'])
with tab_quality:
    st.subheader('Best picks by quality')
    st.dataframe(quality.head(50), use_container_width=True, hide_index=True)
with tab_stakes:
    st.subheader('Smart stake plan')
    st.dataframe(sizing.head(50), use_container_width=True, hide_index=True)
with tab_review:
    st.subheader('Review summary')
    st.dataframe(review_stats, use_container_width=True, hide_index=True)
    st.subheader('Review queue')
    st.dataframe(review_queue.head(100), use_container_width=True, hide_index=True)
with tab_health:
    st.subheader('Data health checks')
    st.dataframe(data_health_frame(active), use_container_width=True, hide_index=True)
with tab_fresh:
    st.subheader('Freshness checks')
    st.dataframe(freshness, use_container_width=True, hide_index=True)
with tab_ledger:
    st.subheader('Proof ledger summary')
    st.json(ledger_stats)
    st.write('Hash chain:', 'valid' if verification.valid else verification.message)

bundle = {
    'data_health': health,
    'freshness': fresh_stats,
    'quality': quality_stats,
    'sizing': sizing_stats,
    'lock': lock_stats,
    'ledger': ledger_stats,
    'warnings': warnings,
}
st.download_button('Download command center summary JSON', json.dumps(bundle, indent=2, default=str), file_name=f'{profile.user_id}_command_center_summary.json', mime='application/json')

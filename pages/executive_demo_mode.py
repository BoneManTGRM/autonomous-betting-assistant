from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bet_sizing import build_bet_sizing_frame
from autonomous_betting_agent.buyer_report import buyer_demo_markdown
from autonomous_betting_agent.freshness import build_freshness_frame, freshness_score, freshness_summary
from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.pick_quality import build_pick_quality_frame
from autonomous_betting_agent.proof_ledger import ledger_summary, load_ledger, sport_breakdown, verify_hash_chain

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'

st.set_page_config(page_title='Executive Demo Mode', layout='wide')
st.title('Executive Demo Mode')
st.caption('Polished view for buyers, investors, influencers, and serious users. Hides messy dev details and shows value, proof, limits, and roadmap.')

profile = current_user_from_session(st.session_state)
ledger = load_ledger(profile.user_id)
try:
    memory_bank = json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8')) if MEMORY_BANK_PATH.exists() else {}
except Exception:
    memory_bank = {}
patterns = memory_bank.get('patterns', []) if isinstance(memory_bank, dict) else []
memory_summary = memory_bank.get('summary', {}) if isinstance(memory_bank, dict) else {}
memory_summary['training_mode'] = memory_bank.get('training_mode', 'N/A') if isinstance(memory_bank, dict) else 'N/A'

summary = ledger_summary(ledger)
verification = verify_hash_chain(ledger)
quality = build_pick_quality_frame(ledger, patterns) if not ledger.empty else pd.DataFrame()
sizing = build_bet_sizing_frame(quality, score_quality=False) if not quality.empty else pd.DataFrame()
freshness = build_freshness_frame(ledger, memory_bank=memory_bank)

hero = st.columns(5)
hero[0].metric('Proof Picks', summary['total_picks'])
hero[1].metric('Win Rate', '' if summary['win_rate'] is None else f"{summary['win_rate']:.1%}")
hero[2].metric('ROI', 'N/A' if summary['roi_percent'] is None else f"{summary['roi_percent']:.2f}%")
hero[3].metric('Hash Chain', 'Valid' if verification.valid else 'Warning')
hero[4].metric('Freshness', f'{freshness_score(freshness)}/100')

st.subheader('Product Summary')
st.write('Audited sports intelligence platform with prediction scoring, odds lock snapshots, local multi-user profiles, tamper-evident proof ledgers, security checks, learning memory, smart stake sizing, and buyer-ready reporting.')

st.subheader('Best Current Proof')
if ledger.empty:
    st.warning('No proof-ledger rows yet. Add official locked picks for a stronger demo.')
else:
    if not quality.empty:
        cols = [col for col in ['event', 'sport', 'prediction', 'pick_quality_score', 'pick_quality_grade', 'recommended_units', 'result_status', 'profit_units'] if col in sizing.columns]
        st.dataframe(sizing[cols].head(20) if cols else sizing.head(20), use_container_width=True, hide_index=True)
    st.subheader('Sport Strengths')
    st.dataframe(sport_breakdown(ledger), use_container_width=True, hide_index=True)

st.subheader('Learning Memory')
st.json(memory_summary)

st.subheader('Known Limitations')
st.write([
    'Current local profiles are not secure cloud accounts.',
    'Rows missing odds/probability should not count as official ROI proof.',
    'The high-confidence training set used fallback probabilities because odds/probability were missing.',
    'More forward-tested, timestamped picks are needed before aggressive valuation claims.',
])

st.subheader('Roadmap to Commercial Version')
st.write([
    'Managed database and real authentication.',
    'Stripe subscriptions.',
    'Automated cross-sport final-result grading.',
    'Closing-line odds collection.',
    'Email/Telegram alerts for A+ picks and graded results.',
])

report = buyer_demo_markdown(ledger=ledger, memory_summary=memory_summary)
st.download_button('Generate Buyer Demo Pack: Markdown report', report, file_name=f'{profile.user_id}_executive_demo_report.md', mime='text/markdown')
if not ledger.empty:
    st.download_button('Generate Buyer Demo Pack: Proof ledger CSV', ledger.to_csv(index=False), file_name=f'{profile.user_id}_proof_ledger.csv', mime='text/csv')
if not quality.empty:
    st.download_button('Generate Buyer Demo Pack: Pick quality CSV', quality.to_csv(index=False), file_name=f'{profile.user_id}_pick_quality.csv', mime='text/csv')
st.download_button('Generate Buyer Demo Pack: Memory JSON', json.dumps(memory_bank, indent=2), file_name=f'{profile.user_id}_learning_memory.json', mime='application/json')

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.proof_ledger import ledger_summary, load_ledger, sport_breakdown, verify_hash_chain

st.set_page_config(page_title='Investor Mode', layout='wide')
st.title('Investor Mode')
st.caption('Generate a buyer/investor-ready snapshot from the local proof ledger.')

profile = current_user_from_session(st.session_state)
ledger = load_ledger(profile.user_id)
summary = ledger_summary(ledger)
verification = verify_hash_chain(ledger)
breakdown = sport_breakdown(ledger)

st.subheader('Product positioning')
st.write('Audited sports intelligence platform with timestamped predictions, odds capture, ROI tracking, local multi-user profiles, security checks, and proof-ledger verification.')

cols = st.columns(6)
cols[0].metric('Proof picks', summary['total_picks'])
cols[1].metric('Win rate', '' if summary['win_rate'] is None else f"{summary['win_rate']:.1%}")
cols[2].metric('ROI', '' if summary['roi_percent'] is None else f"{summary['roi_percent']:.2f}%")
cols[3].metric('Units', f"{summary['units']:.2f}")
cols[4].metric('A+ picks', summary['a_plus'])
cols[5].metric('Hash chain', 'Valid' if verification.valid else 'Warning')

st.subheader('Investor checklist')
checklist = pd.DataFrame([
    {'area': 'Prediction engine', 'status': 'Built', 'note': 'Sports prediction/reporting workflow exists.'},
    {'area': 'Odds normalization', 'status': 'Built', 'note': 'Alternate odds/probability columns are normalized.'},
    {'area': 'Audit enrichment', 'status': 'Built', 'note': 'Adds confidence tiers, ROI/unit fields, and grading labels.'},
    {'area': 'Proof ledger', 'status': 'Built', 'note': 'Timestamped local ledger with row hash chain.'},
    {'area': 'Public dashboard', 'status': 'Built', 'note': 'Read-only local performance dashboard.'},
    {'area': 'Security center', 'status': 'Built', 'note': 'Defensive CSV/upload checks and safer exports.'},
    {'area': 'Local multi-user', 'status': 'Built', 'note': 'Profile separation without auth or cloud server.'},
    {'area': 'Cloud auth/subscriptions', 'status': 'Not yet', 'note': 'Deferred intentionally.'},
    {'area': 'Fully automatic cross-sport grading', 'status': 'Partial', 'note': 'Depends on results API coverage.'},
])
st.dataframe(checklist, use_container_width=True, hide_index=True)

st.subheader('Sport breakdown')
st.dataframe(breakdown, use_container_width=True, hide_index=True)

snapshot = {
    'generated_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'local_user_id': profile.user_id,
    'local_user_display_name': profile.display_name,
    'positioning': 'Audited sports intelligence platform with timestamped predictions, odds capture, ROI tracking, security checks, and proof-ledger verification.',
    'summary': summary,
    'hash_chain': verification.__dict__,
    'investor_checklist': checklist.to_dict(orient='records'),
    'sport_breakdown': breakdown.to_dict(orient='records') if not breakdown.empty else [],
}

st.subheader('Buyer package downloads')
st.download_button('Download investor snapshot JSON', json.dumps(snapshot, indent=2), file_name=f'{profile.user_id}_investor_snapshot.json', mime='application/json')
if not ledger.empty:
    st.download_button('Download proof ledger CSV', ledger.to_csv(index=False), file_name=f'{profile.user_id}_proof_ledger.csv', mime='text/csv')
    st.download_button('Download sport breakdown CSV', breakdown.to_csv(index=False), file_name=f'{profile.user_id}_sport_breakdown.csv', mime='text/csv')

with st.expander('Suggested buyer pitch', expanded=True):
    st.write('This is not just a betting predictor. It is an audited sports analytics platform with local multi-user profiles, timestamped predictions, odds normalization, tamper-evident ledgers, security checks, ROI tracking, and public performance dashboards. The remaining commercial layer is auth, billing, managed database, and broader automated result coverage.')

with st.expander('What must be proven before asking for $100k+', expanded=False):
    st.write(
        {
            'sample_size': 'Hundreds to thousands of timestamped picks.',
            'profitability': 'Positive ROI after odds, not just high win rate.',
            'audit_integrity': 'Hash-chain verification stays valid.',
            'retention': 'Users return because alerts/results are useful.',
            'revenue': 'Even $3k-$5k MRR makes a $100k valuation much easier to defend.',
        }
    )

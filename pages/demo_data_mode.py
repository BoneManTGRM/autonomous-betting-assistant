from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.data_intake_gate import intake_gate
from autonomous_betting_agent.quality_control import build_quality_control_report
from autonomous_betting_agent.review_packet import build_review_packet, packet_markdown

DEMO_ROWS = [
    {
        'event': 'Team A at Team B',
        'sport': 'Demo League',
        'market_type': 'moneyline',
        'prediction': 'Team B',
        'model_probability': 0.62,
        'decimal_price': 1.95,
        'bookmaker': 'DemoBook',
        'odds_source': 'DemoOdds',
        'prediction_timestamp': '2026-06-15T18:00:00Z',
        'known_start_utc': '2026-06-15T22:00:00Z',
        'decision': 'play',
        'confidence_tier': 'A',
        'model_version': 'demo-v1',
        'calibration_version': 'demo-cal-v1',
        'memory_version': 'demo-memory-v1',
        'api_bundle_version': 'demo-api-v1',
        'result_status': 'win',
        'final_score': '3-1',
        'winner': 'Team B',
        'stake_units': 1,
        'profit_units': 0.95,
        'closing_decimal_price': 1.80,
        'graded_at_utc': '2026-06-16T02:00:00Z',
    },
    {
        'event': 'Team C at Team D',
        'sport': 'Demo League',
        'market_type': 'moneyline',
        'prediction': 'Team C',
        'model_probability': 0.58,
        'decimal_price': 2.05,
        'bookmaker': 'DemoBook',
        'odds_source': 'DemoOdds',
        'prediction_timestamp': '2026-06-15T19:00:00Z',
        'known_start_utc': '2026-06-15T23:00:00Z',
        'decision': 'play',
        'confidence_tier': 'B',
        'model_version': 'demo-v1',
        'calibration_version': 'demo-cal-v1',
        'memory_version': 'demo-memory-v1',
        'api_bundle_version': 'demo-api-v1',
        'result_status': 'loss',
        'final_score': '2-0',
        'winner': 'Team D',
        'stake_units': 1,
        'profit_units': -1,
        'closing_decimal_price': 2.20,
        'graded_at_utc': '2026-06-16T03:00:00Z',
    },
]

st.set_page_config(page_title='Demo Data Mode', layout='wide')
st.title('Demo Data Mode')
st.caption('Safe sample data that demonstrates the workflow without exposing private rows.')

demo = pd.DataFrame(DEMO_ROWS)
intake = intake_gate(demo)
quality = build_quality_control_report(demo)
packet = build_review_packet(demo)
markdown = packet_markdown(packet)

cols = st.columns(5)
cols[0].metric('Rows', len(demo))
cols[1].metric('Intake Status', intake['overall_status'])
cols[2].metric('Quality Score', f"{quality['quality_score']}/100")
cols[3].metric('Wins', packet['statistics']['wins'])
cols[4].metric('Losses', packet['statistics']['losses'])

st.subheader('Demo rows')
st.dataframe(demo, use_container_width=True, hide_index=True)

st.subheader('Demo review packet')
st.markdown(markdown)

st.download_button('Download demo CSV', demo.to_csv(index=False), file_name='demo_workflow_data.csv', mime='text/csv')
st.download_button('Download demo review packet Markdown', markdown, file_name='demo_review_packet.md', mime='text/markdown')

from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.report_studio_legacy_notice import render_legacy_report_notice
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Learning Report Studio', layout='wide')
LANG = render_app_sidebar('report_learning_studio', language_key='report_studio_language', selector='radio')

st.title('Learning Report Studio')
render_legacy_report_notice(LANG)
st.page_link('pages/report_studio.py', label='Open unified Report Studio')
st.caption('The unified Report Studio now includes the learning audit, calibration diagnostics, official proof status, image exports, and app feed.')

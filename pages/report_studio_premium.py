from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.report_studio_legacy_notice import render_legacy_report_notice
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Report Studio Premium', layout='wide')
LANG = render_app_sidebar('report_studio_premium', language_key='report_studio_language', selector='radio')

st.title('Report Studio Premium')
render_legacy_report_notice(LANG)
st.page_link('pages/report_studio.py', label='Open unified Report Studio', icon='📊')
st.caption('This compatibility page now routes production reporting to the unified Report Studio.')

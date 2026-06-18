from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='ABA Signal Pro', layout='wide', initial_sidebar_state='expanded')
render_app_sidebar('home', language_key='global_language', selector='radio')

st.title('ABA Signal Pro')
st.caption('Powered by Reparodynamics')
st.info('Use the Tools menu to move between pages.')

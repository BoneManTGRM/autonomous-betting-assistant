from __future__ import annotations

import streamlit as st

APP_NAME = "ARA Signal Pro"
APP_TAGLINE = "Powered by Reparodynamics"

st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Brand stays at the top of the sidebar.
st.sidebar.markdown("### :green[ARA] Signal :red[Pro]")
st.sidebar.caption(APP_TAGLINE)
st.sidebar.markdown("---")

PAGES = [
    st.Page("pages/pro_predictor.py", title="Pro Predictor"),
    st.Page("pages/ultra80_profit_mode.py", title="Ultra 70 Profit Mode"),
    st.Page("pages/simulation_lab.py", title="Simulation Lab"),
    st.Page("pages/threshold_optimizer.py", title="Threshold Optimizer"),
    st.Page("pages/what_are_the_odds.py", title="What Are the Odds"),
    st.Page("pages/odds_lock_pro.py", title="Odds Lock Pro"),
    st.Page("pages/public_proof_dashboard.py", title="Public Proof Dashboard"),
    st.Page("pages/learn_memory.py", title="Learning Memory"),
    st.Page("pages/reset_lock_file.py", title="Reset Lock File"),
]

# Curated navigation must stay visible in the sidebar. Do not disable
# [client].showSidebarNavigation in .streamlit/config.toml.
current_page = st.navigation(PAGES, position="sidebar", expanded=True)


def _ignore_late_page_config(*args, **kwargs):
    return None


# Existing page files still call set_page_config; ignore those after the main app config.
st.set_page_config = _ignore_late_page_config
current_page.run()

# Explainer stays at the bottom of the sidebar after page controls render.
st.sidebar.markdown("---")
st.sidebar.markdown("### Workflow")
st.sidebar.caption("Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory.")
st.sidebar.caption("Odds Lock Pro timestamps locked picks; Public Proof Dashboard shows ROI and results.")

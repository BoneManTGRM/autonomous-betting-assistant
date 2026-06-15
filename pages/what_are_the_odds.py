from __future__ import annotations

import streamlit as st

import autonomous_betting_agent  # noqa: F401  # installs global sidebar/report translator
from autonomous_betting_agent.odds_breakdown import render_odds_breakdown_section

st.set_page_config(page_title="What Are the Odds", layout="wide")

# The global sidebar patch turns this into the single shared language selector.
st.sidebar.selectbox("Language / Idioma", ["English", "Español"], key="what_are_the_odds_language")

render_odds_breakdown_section("what_are_the_odds")

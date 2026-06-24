from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bankroll import suggest_stake
from autonomous_betting_agent.correlation import correlation_warnings
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage

st.set_page_config(page_title="Local Bankroll Risk", layout="wide")
render_app_sidebar("local_bankroll_risk", language_key="local_bankroll_risk_language")
require_streamlit_access(st, allow_roles={"admin"})

st.title("Local Bankroll Risk")
st.caption("Local risk-management review only. This page does not provide financial advice or guarantee outcomes.")

store = LocalStorage()
rows = store.load_rows()
if not rows:
    st.info("No local rows found yet.")
    st.stop()

with st.sidebar:
    bankroll = st.number_input("Bankroll units", min_value=1.0, value=100.0, step=10.0)
    mode = st.selectbox("Stake mode", ["flat", "conservative_kelly"])
    flat_units = st.number_input("Flat stake units", min_value=0.1, value=1.0, step=0.1)
    max_daily = st.number_input("Max daily exposure %", min_value=0.1, max_value=100.0, value=5.0, step=0.5) / 100.0
    max_sport = st.number_input("Max sport exposure %", min_value=0.1, max_value=100.0, value=5.0, step=0.5) / 100.0
    max_event = st.number_input("Max event exposure %", min_value=0.1, max_value=100.0, value=2.0, step=0.5) / 100.0

warnings = correlation_warnings(rows)
if warnings:
    st.subheader("Correlation warnings")
    for warning in warnings:
        st.warning(warning)
else:
    st.success("No duplicate/correlation warnings detected from local rows.")

st.subheader("Stake suggestions")
review_rows = []
for row in rows:
    suggestion = suggest_stake(
        row,
        bankroll=float(bankroll),
        mode=mode,
        flat_units=float(flat_units),
        max_daily_exposure_pct=float(max_daily),
        max_sport_exposure_pct=float(max_sport),
        max_event_exposure_pct=float(max_event),
    )
    output = dict(row)
    output["suggested_stake_units"] = suggestion.stake
    output["stake_blocked"] = suggestion.blocked
    output["stake_reason"] = suggestion.reason
    review_rows.append(output)

st.dataframe(pd.DataFrame(review_rows), use_container_width=True)

st.subheader("Cooldown and drawdown placeholders")
st.write({
    "losing_streak_cooldown": "Placeholder: reduce or stop suggested stake after a configured losing streak.",
    "drawdown_protection": "Placeholder: reduce or stop suggested stake after bankroll drawdown reaches a configured threshold.",
})

st.warning("Risk-management helper only. No suggested stake guarantees a result or return.")

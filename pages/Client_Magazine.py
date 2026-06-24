from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.api_config import api_status
from autonomous_betting_agent.bet_catalog import build_bet_catalog, render_betting_magazine, render_pick_card
from autonomous_betting_agent.chain_core import build_candidate_chains
from autonomous_betting_agent.client_profiles import normalize_client_profile
from autonomous_betting_agent.context_cards import render_row_context, render_script_chain_card_with_context
from autonomous_betting_agent.external_context import apply_context_to_pick, collect_external_context
from autonomous_betting_agent.script_chain_core import ScriptChainResult, build_same_game_chain_from_script, build_target_payout_chain
from autonomous_betting_agent.script_chain_report import render_game_script_chain_section
from autonomous_betting_agent.source_key_panel import render_optional_context_source_panel

st.set_page_config(page_title="Client Magazine", layout="wide")
st.title("Client Magazine")
st.caption("Local-first analytics and report generation only. No execution and no guaranteed outcomes.")

uploaded = st.file_uploader("Upload candidate rows CSV", type=["csv"])

with st.sidebar:
    st.header("Client Profile")
    name = st.text_input("Name", "Default Client")
    risk_profile = st.selectbox("Mode", ["conservative", "balanced", "aggressive"], index=1)
    unit_size = st.number_input("Unit size", min_value=0.0, value=1.0, step=0.25)
    max_single = st.number_input("Max single exposure", min_value=0.0, value=1.0, step=0.25)
    max_chain_legs = st.slider("Max combined legs", 2, 4, 2 if risk_profile == "conservative" else 3)
    allow_chains = st.checkbox("Allow combined rows", value=True)
    allow_player_markets = st.checkbox("Allow player markets", value=(risk_profile != "conservative"))
    allow_hr_markets = st.checkbox("Allow HR markets", value=(risk_profile == "aggressive"))
    st.header("External Context")
    force_local_only = st.checkbox("Force local CSV-only mode", value=False)
    render_optional_context_source_panel(st, expanded=False)
    enable_api_football = st.checkbox("Enable API-Football context", value=True)
    enable_perplexity = st.checkbox("Enable Perplexity research", value=True)
    enable_newsapi = st.checkbox("Enable NewsAPI recent news", value=True)
    show_external_context = st.checkbox("Show external context in cards", value=True)
    st.header("Game Script Chains")
    enable_script_chains = st.checkbox("Enable game-script chains", value=True)
    enable_target_payout = st.checkbox("Enable target-payout chains", value=True)
    stake_amount = st.number_input("Stake amount", min_value=0.0, value=1.0, step=1.0)
    target_payout = st.number_input("Target payout", min_value=0.0, value=2.0, step=1.0)
    min_chain_probability = st.slider("Minimum adjusted probability", 0.0, 1.0, 0.25, 0.01)
    max_risk_score = st.slider("Maximum chain risk score", 1.0, 10.0, 8.0, 0.5)

status = api_status()
st.sidebar.caption("API status: " + "; ".join(f"{k}: {v}" for k, v in status.items()))

profile = normalize_client_profile({
    "name": name,
    "risk_profile": risk_profile,
    "unit_size": unit_size,
    "max_single_exposure": max_single,
    "max_chain_legs": max_chain_legs,
    "allow_chains": allow_chains,
    "allow_player_markets": allow_player_markets,
    "allow_hr_markets": allow_hr_markets,
})

if uploaded is None:
    st.info("Upload a CSV with game, selection, price, model_probability, and analysis fields to generate the magazine.")
    st.stop()

rows_df = pd.read_csv(uploaded)
rows = rows_df.fillna("").to_dict(orient="records")

if not force_local_only:
    enriched_rows = []
    for row in rows:
        context = collect_external_context(row, enable_api_football=enable_api_football, enable_perplexity=enable_perplexity, enable_newsapi=enable_newsapi)
        enriched_rows.append(apply_context_to_pick(row, context))
    rows = enriched_rows
else:
    st.warning("Local CSV-only mode enabled. External API context skipped.")

st.subheader("Imported Rows")
st.dataframe(pd.DataFrame(rows), use_container_width=True)

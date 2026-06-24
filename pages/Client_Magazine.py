from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bet_catalog import build_bet_catalog, render_betting_magazine, render_pick_card
from autonomous_betting_agent.chain_core import build_candidate_chains
from autonomous_betting_agent.client_profiles import normalize_client_profile
from autonomous_betting_agent.script_chain_core import ScriptChainResult, build_same_game_chain_from_script, build_target_payout_chain
from autonomous_betting_agent.script_chain_report import render_game_script_chain_section, render_script_chain_card

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
    st.header("Game Script Chains")
    enable_script_chains = st.checkbox("Enable game-script chains", value=True)
    enable_target_payout = st.checkbox("Enable target-payout chains", value=True)
    stake_amount = st.number_input("Stake amount", min_value=0.0, value=1.0, step=1.0)
    target_payout = st.number_input("Target payout", min_value=0.0, value=2.0, step=1.0)
    min_chain_probability = st.slider("Minimum adjusted probability", 0.0, 1.0, 0.25, 0.01)
    max_risk_score = st.slider("Maximum chain risk score", 1.0, 10.0, 8.0, 0.5)

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

st.subheader("Imported Rows")
st.dataframe(rows_df, use_container_width=True)

chain_groups = build_candidate_chains(rows, profile)
chain_rows = []
if isinstance(chain_groups, dict):
    for value in chain_groups.values():
        if isinstance(value, list):
            chain_rows.extend(chain.as_row() for chain in value)

script_chains: list[ScriptChainResult] = []
if enable_script_chains:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        key = str(row.get("game") or row.get("event") or row.get("event_name") or row.get("matchup") or "Unknown")
        grouped.setdefault(key, []).append(row)
    for game_rows in grouped.values():
        event = game_rows[0]
        result = build_target_payout_chain(event, game_rows, stake_amount, target_payout, profile, minimum_probability=min_chain_probability, maximum_risk_score=max_risk_score) if enable_target_payout else build_same_game_chain_from_script(event, game_rows, profile)
        if isinstance(result, ScriptChainResult):
            script_chains.append(result)

script_chain_rows = [chain.as_row() for chain in script_chains]
all_rows = rows + chain_rows + script_chain_rows
catalog = build_bet_catalog(all_rows)
magazine = render_betting_magazine(all_rows, subscriber_name=profile.name) + "\n" + render_game_script_chain_section(script_chains)

st.subheader("Catalog Sections")
for section, picks in catalog.items():
    with st.expander(f"{section} ({len(picks)})", expanded=section in {"Best 65%+ Singles", "Conservative Baseball Chains"}):
        if not picks:
            st.write("No qualifying rows in this section.")
        for pick in picks:
            st.markdown(render_pick_card(pick))
            st.divider()

st.subheader("Best Game-Script Chains")
if not script_chains:
    st.write("NO CHAIN RECOMMENDED")
for chain in script_chains:
    st.markdown(render_script_chain_card(chain))
    st.divider()

st.subheader("Magazine")
st.download_button("Download Markdown", magazine, file_name="client_magazine.md", mime="text/markdown")
st.download_button("Download HTML", "<pre>" + magazine.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre>", file_name="client_magazine.html", mime="text/html")

flat_catalog = []
for section, picks in catalog.items():
    for pick in picks:
        row = pick.as_dict()
        row["section"] = section
        flat_catalog.append(row)
for chain in script_chains:
    row = chain.as_row()
    row["section"] = "Best Game-Script Chains"
    flat_catalog.append(row)
if flat_catalog:
    export_df = pd.DataFrame(flat_catalog)
    st.download_button("Download Catalog CSV", export_df.to_csv(index=False), file_name="client_catalog.csv", mime="text/csv")

st.text_area("Preview", magazine, height=500)

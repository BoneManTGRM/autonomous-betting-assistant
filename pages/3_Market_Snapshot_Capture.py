from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.market_snapshots import append_snapshot_csv, latest_snapshot_with_movement, summaries_to_snapshot_frame

st.set_page_config(page_title="Market Snapshot Capture", layout="wide")
st.title("Market Snapshot Capture")
st.caption("One-button line-movement capture using The Odds API only.")


def secret_or_env(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, "") or "")


def explain_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "API key rejected"
    if status == 422:
        return "sport, market, or region not available"
    if status == 429:
        return "API quota or rate limit reached"
    return str(exc) or "request failed"


@st.cache_data(ttl=900, show_spinner=False)
def cached_sports(api_key: str):
    return list_sports(api_key, include_all=False)


api_key = st.sidebar.text_input("The Odds API key", value="", type="password") or secret_or_env("THE_ODDS_API_KEY")
regions = st.sidebar.multiselect("Regions", ["us", "us2", "uk", "eu", "au"], default=["us", "us2", "uk", "eu"])
max_events = st.sidebar.number_input("Max events", min_value=1, max_value=100, value=50)
snapshot_path = st.sidebar.text_input("Snapshot CSV path", "data/market_snapshots.csv")
latest_path = st.sidebar.text_input("Latest movement CSV path", "data/latest_market_movement.csv")

if not api_key:
    st.warning("Enter The Odds API key or set THE_ODDS_API_KEY.")
    st.stop()

try:
    sports = cached_sports(api_key)
except Exception as exc:
    st.error(f"Could not load sports: {explain_error(exc)}")
    st.stop()

sport_options = {f"{sport.title} | {sport.key}": sport.key for sport in sports if not sport.has_outrights}
if not sport_options:
    st.error("No active non-outright sports returned by The Odds API.")
    st.stop()

choice = st.selectbox("Sport feed", list(sport_options.keys()))
sport_key = sport_options[choice]

if st.button("Capture snapshot", type="primary"):
    if not regions:
        st.error("Choose at least one region.")
        st.stop()
    with st.spinner("Capturing market snapshot"):
        try:
            summaries = scan_market(api_key, sport_key=sport_key, regions=",".join(regions), max_events=int(max_events))
            snapshot = summaries_to_snapshot_frame(summaries)
            combined = append_snapshot_csv(snapshot, Path(snapshot_path))
            latest = latest_snapshot_with_movement(combined)
            latest_output = Path(latest_path)
            latest_output.parent.mkdir(parents=True, exist_ok=True)
            latest.to_csv(latest_output, index=False)
        except Exception as exc:
            st.error(f"Capture failed: {explain_error(exc)}")
            st.stop()

    st.success(f"Captured {len(snapshot)} rows for {sport_key}.")
    col1, col2, col3 = st.columns(3)
    col1.metric("Snapshot rows", len(snapshot))
    col2.metric("Total stored rows", len(combined))
    col3.metric("Latest movement rows", len(latest))

    st.write("Latest line movement")
    st.dataframe(latest, use_container_width=True, hide_index=True)
    st.download_button("Download latest movement CSV", latest.to_csv(index=False), file_name="latest_market_movement.csv", mime="text/csv")

    with st.expander("Raw snapshot rows"):
        st.dataframe(snapshot, use_container_width=True, hide_index=True)
        st.download_button("Download this snapshot CSV", snapshot.to_csv(index=False), file_name="market_snapshot.csv", mime="text/csv")
else:
    st.info("Choose a sport and press Capture snapshot. Run it repeatedly over time to build opening, current, and closing movement.")

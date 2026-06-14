from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import streamlit as st

from autonomous_betting_agent.multi_source_fusion import fuse_row


@dataclass(frozen=True)
class PredictorProConfig:
    game: str
    scan_target: str
    sport_search: str
    venue_city: str
    book_regions: list[str]
    markets: list[str]
    max_sport_feeds: int
    max_events_per_feed: int
    odds_api_enabled: bool
    sportsdataio_enabled: bool
    weatherapi_enabled: bool
    use_ara_memory: bool


def _status(value: bool) -> str:
    return "Enabled" if value else "Missing"


def _pct(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value * 100:.1f}%"


st.set_page_config(page_title="Pro Predictor", page_icon="📊", layout="wide")

st.title("Pro Predictor")
st.caption(
    "Multi-source all-sports predictor. It combines sportsbook odds, SportsDataIO stats/context, "
    "WeatherAPI conditions, and ARA learning memory through a capped fusion layer. "
    "Research-only; no guaranteed winners."
)

st.info(
    "How to read it: sportsbook odds create the base market probability. Sports/team data, "
    "injuries/lineups, weather/context, and ARA memory can adjust that probability only within capped limits."
)

st.subheader("1. API sources")
api1, api2, api3 = st.columns(3)
with api1:
    use_odds_api = st.toggle("Use Odds API", value=True)
    odds_api_key = st.text_input("Odds API key", type="password", help="Used for market probability, best price, book count, and CLV.")
with api2:
    use_sportsdataio = st.toggle("Use SportsDataIO", value=True)
    sportsdataio_key = st.text_input("SportsDataIO key", type="password", help="Used for schedules, scores, team/player data, injuries and lineups.")
with api3:
    use_weatherapi = st.toggle("Use WeatherAPI", value=True)
    weatherapi_key = st.text_input("WeatherAPI key", type="password", help="Used for weather, wind, rain, temperature and venue context.")

st.subheader("2. Game setup")
setup1, setup2 = st.columns(2)
with setup1:
    game = st.text_input("Game", value="Mexico vs South Korea")
    scan_target = st.radio("Scan target", ["All sports", "One league/sport", "One team/player"], horizontal=True)
    sport_search = st.text_input("Sport/feed search", value="soccer")
with setup2:
    venue_city = st.text_input("Weather location / venue city", value="")
    league_hint = st.text_input("League / competition hint", value="", placeholder="Example: international, fifa, nba, nfl")
    use_ara_memory = st.toggle("Use ARA learning memory", value=True)

st.subheader("3. Provider controls")
ctl1, ctl2 = st.columns(2)
with ctl1:
    book_regions = st.multiselect("Bookmaker regions", ["us", "us2", "uk", "eu", "au"], default=["us", "eu", "uk"])
    markets = st.multiselect("Markets", ["h2h", "spreads", "totals"], default=["h2h", "spreads", "totals"])
with ctl2:
    max_sport_feeds = st.number_input("Max sport feeds", min_value=1, max_value=100, value=30, step=1)
    max_events_per_feed = st.number_input("Max events per feed", min_value=1, max_value=100, value=25, step=1)

with st.expander("Manual signal preview", expanded=False):
    st.caption("These preview fields let you see the fusion math before live API results are available.")
    sig1, sig2, sig3 = st.columns(3)
    with sig1:
        market_prob = st.number_input("Market probability %", min_value=1.0, max_value=99.0, value=56.2, step=0.1)
        stats_prob = st.number_input("Stats model probability %", min_value=1.0, max_value=99.0, value=58.3, step=0.1)
    with sig2:
        injury_risk_score = st.number_input("Injury/lineup risk score", min_value=0.0, max_value=100.0, value=86.0, step=1.0)
        key_player_out = st.toggle("Key player out", value=False)
    with sig3:
        weather_risk_score = st.number_input("Weather risk score", min_value=0.0, max_value=100.0, value=92.0, step=1.0)
        memory_roi = st.number_input("ARA memory bucket ROI %", min_value=-100.0, max_value=100.0, value=0.0, step=0.5)

st.subheader("4. Source status")
s1, s2, s3, s4 = st.columns(4)
s1.metric("Odds API", _status(use_odds_api and bool(odds_api_key.strip())))
s2.metric("SportsDataIO", _status(use_sportsdataio and bool(sportsdataio_key.strip())))
s3.metric("WeatherAPI", _status(use_weatherapi and bool(weatherapi_key.strip())))
s4.metric("ARA memory", "Enabled" if use_ara_memory else "Off")

config = PredictorProConfig(
    game=game,
    scan_target=scan_target,
    sport_search=sport_search,
    venue_city=venue_city,
    book_regions=book_regions,
    markets=markets,
    max_sport_feeds=int(max_sport_feeds),
    max_events_per_feed=int(max_events_per_feed),
    odds_api_enabled=use_odds_api and bool(odds_api_key.strip()),
    sportsdataio_enabled=use_sportsdataio and bool(sportsdataio_key.strip()),
    weatherapi_enabled=use_weatherapi and bool(weatherapi_key.strip()),
    use_ara_memory=use_ara_memory,
)

run_button = st.button("Run multi-API Predictor Pro", type="primary", use_container_width=True)

if run_button:
    fusion_row = {
        "market_probability": market_prob / 100.0 if config.odds_api_enabled else "",
        "stats_probability": stats_prob / 100.0 if config.sportsdataio_enabled else "",
        "injury_risk_score": injury_risk_score if config.sportsdataio_enabled else "",
        "key_player_out": str(key_player_out).lower() if config.sportsdataio_enabled else "",
        "weather_risk_score": weather_risk_score if config.weatherapi_enabled else "",
        "bucket_roi": memory_roi / 100.0 if config.use_ara_memory else "",
    }
    fused = fuse_row(fusion_row)

    st.subheader("Fusion output")
    out1, out2, out3, out4 = st.columns(4)
    out1.metric("Market probability", _pct(fused.market_probability))
    out2.metric("Final probability", _pct(fused.final_probability))
    out3.metric("Reliability", f"{fused.reliability_score}/100")
    out4.metric("Confidence", fused.confidence.title())

    st.subheader("Why the score moved")
    move_cols = st.columns(4)
    move_cols[0].metric("Stats adjustment", _pct(fused.stats_adjustment))
    move_cols[1].metric("Injury adjustment", _pct(fused.injury_adjustment))
    move_cols[2].metric("Weather adjustment", _pct(fused.weather_adjustment))
    move_cols[3].metric("ARA memory adjustment", _pct(fused.ara_memory_adjustment))

    if fused.fusion_warning:
        st.warning(fused.fusion_warning)
    st.write("Reason codes:")
    st.write(fused.fusion_reason)

    if not config.odds_api_enabled:
        st.warning("Odds API is missing. The market-probability foundation is unavailable.")
    if not config.sportsdataio_enabled:
        st.warning("SportsDataIO is missing. Stats, injury, lineup and score context are limited.")
    if not config.weatherapi_enabled:
        st.info("WeatherAPI is missing. Weather/context adjustment will stay neutral unless weather fields already exist in uploaded data.")

    st.subheader("Run config")
    st.code(json.dumps(asdict(config), indent=2), language="json")
else:
    st.info("Add all available API keys, enter the game and sport/feed search, then run the multi-API fusion layer.")

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class DecisionConfig:
    game: str
    sport_search: str
    venue_city: str
    book_regions: list[str]
    markets: list[str]
    max_sport_feeds: int
    max_events_per_feed: int
    odds_api_enabled: bool
    weatherapi_enabled: bool
    sportsdataio_enabled: bool


def _mask_status(value: str) -> str:
    return "Provided" if value.strip() else "Missing"


def _risk_label(temp_f: float | None, wind_mph: float | None, rain_mm: float | None) -> tuple[str, int, list[str]]:
    score = 100
    flags: list[str] = []
    if temp_f is not None:
        if temp_f <= 32 or temp_f >= 95:
            score -= 25
            flags.append("extreme temperature")
        elif temp_f <= 40 or temp_f >= 88:
            score -= 10
            flags.append("moderate temperature edge")
    if wind_mph is not None:
        if wind_mph >= 20:
            score -= 30
            flags.append("strong wind")
        elif wind_mph >= 12:
            score -= 12
            flags.append("moderate wind")
    if rain_mm is not None:
        if rain_mm >= 5:
            score -= 20
            flags.append("heavy precipitation")
        elif rain_mm > 0:
            score -= 8
            flags.append("light precipitation")
    score = max(0, min(100, score))
    if score >= 80:
        return "LOW WEATHER RISK", score, flags or ["no major weather concern"]
    if score >= 60:
        return "WATCH WEATHER", score, flags
    return "HIGH WEATHER RISK", score, flags


st.set_page_config(page_title="Odds + Weather Decision Layer", page_icon="📊", layout="wide")

st.title("Odds + Weather Decision Layer")
st.caption("Uses The Odds API, WeatherAPI, and optional SportsDataIO. Fields are shown on-page for faster mobile use.")

with st.expander("API keys", expanded=False):
    api_col1, api_col2, api_col3 = st.columns(3)
    with api_col1:
        odds_api_key = st.text_input("The Odds API key", type="password", help="Required for odds and book-region data.")
    with api_col2:
        weatherapi_key = st.text_input("WeatherAPI key", type="password", help="Required for venue weather intelligence.")
    with api_col3:
        sportsdataio_key = st.text_input("SportsDataIO key", type="password", help="Optional for scores, schedules, injuries, and lineups.")

st.subheader("1. Game setup")
setup_col1, setup_col2 = st.columns(2)
with setup_col1:
    game = st.text_input("Game", value="Mexico vs South Korea")
    sport_search = st.text_input("Sport search", value="soccer")
with setup_col2:
    venue_city = st.text_input("Weather location / venue city", value="")
    league_hint = st.text_input("League / competition hint", value="", placeholder="Example: international, fifa, nba, nfl")

st.subheader("2. Odds setup")
odds_col1, odds_col2 = st.columns(2)
with odds_col1:
    book_regions = st.multiselect("Book regions", ["us", "us2", "uk", "eu", "au"], default=["us", "us2", "uk", "eu"])
    markets = st.multiselect("Markets", ["h2h", "spreads", "totals"], default=["h2h", "spreads", "totals"])
with odds_col2:
    max_sport_feeds = st.number_input("Max sport feeds", min_value=1, max_value=100, value=30, step=1)
    max_events_per_feed = st.number_input("Max events per feed", min_value=1, max_value=100, value=25, step=1)

st.subheader("3. Weather intelligence")
weather_col1, weather_col2, weather_col3 = st.columns(3)
with weather_col1:
    manual_temp_f = st.number_input("Manual temp °F", min_value=-40.0, max_value=130.0, value=70.0, step=1.0)
with weather_col2:
    manual_wind_mph = st.number_input("Manual wind mph", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
with weather_col3:
    manual_rain_mm = st.number_input("Manual rain mm", min_value=0.0, max_value=200.0, value=0.0, step=0.5)

st.subheader("4. Data-source status")
status_col1, status_col2, status_col3 = st.columns(3)
status_col1.metric("Odds API", _mask_status(odds_api_key))
status_col2.metric("WeatherAPI", _mask_status(weatherapi_key))
status_col3.metric("SportsDataIO", _mask_status(sportsdataio_key))

config = DecisionConfig(
    game=game,
    sport_search=sport_search,
    venue_city=venue_city,
    book_regions=book_regions,
    markets=markets,
    max_sport_feeds=int(max_sport_feeds),
    max_events_per_feed=int(max_events_per_feed),
    odds_api_enabled=bool(odds_api_key.strip()),
    weatherapi_enabled=bool(weatherapi_key.strip()),
    sportsdataio_enabled=bool(sportsdataio_key.strip()),
)

run_button = st.button("Run odds + weather layer", type="primary", use_container_width=True)

if run_button:
    label, score, flags = _risk_label(manual_temp_f, manual_wind_mph, manual_rain_mm)
    st.subheader("Decision output")
    out1, out2, out3 = st.columns(3)
    out1.metric("Weather risk", label)
    out2.metric("Weather score", score)
    out3.metric("Markets selected", len(markets))

    if not config.odds_api_enabled:
        st.warning("Odds API key is missing. Odds movement and CLV cannot be calculated yet.")
    if not config.weatherapi_enabled and not venue_city:
        st.warning("WeatherAPI key and venue city are missing. Weather must be entered manually or supplied later.")
    if not config.sportsdataio_enabled:
        st.info("SportsDataIO is optional on this page, but recommended for injuries, schedules, scores, and lineups.")

    st.write("Weather flags:")
    for flag in flags:
        st.write(f"- {flag}")

    st.code(json.dumps(asdict(config), indent=2), language="json")
else:
    st.info("Enter the game, sport, book regions, venue/weather fields, then run the layer.")

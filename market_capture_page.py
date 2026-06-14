from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import streamlit as st

from autonomous_betting_agent.ui_text import LANGUAGES, tr


@dataclass(frozen=True)
class MarketCaptureConfig:
    language: str
    odds_api_enabled: bool
    scan_target: str
    sport_search: str
    game_filter: str
    book_regions: list[str]
    markets: list[str]
    max_sport_feeds: int
    max_events_per_feed: int
    snapshot_label: str
    output_folder: str
    max_api_calls: int
    cache_ttl_seconds: int


def _status(enabled: bool, lang: str) -> str:
    return tr("enabled", lang) if enabled else tr("missing", lang)


st.set_page_config(page_title="Market Capture", page_icon="📈", layout="wide")

language_name = st.selectbox("Language / Idioma", list(LANGUAGES.keys()), index=0)
lang = LANGUAGES[language_name]

st.title(tr("market_snapshot_title", lang))
st.caption(tr("market_snapshot_caption", lang))

st.subheader(tr("api_sources", lang))
api_col1, api_col2 = st.columns([2, 1])
with api_col1:
    odds_api_key = st.text_input(tr("odds_api_key", lang), type="password")
with api_col2:
    st.metric("Odds API", _status(bool(odds_api_key.strip()), lang))

st.subheader(tr("game_setup", lang))
setup1, setup2 = st.columns(2)
with setup1:
    scan_options = [tr("all_sports", lang), tr("one_league", lang), tr("one_team", lang)]
    scan_target = st.radio(tr("scan_target", lang), scan_options, horizontal=True)
    sport_search = st.text_input(tr("sport_search", lang), value="auto")
with setup2:
    game_filter = st.text_input(tr("game", lang), value="", placeholder="Mexico vs South Korea")
    league_hint = st.text_input(tr("league_hint", lang), value="", placeholder="fifa, soccer, nfl, nba")

st.subheader(tr("snapshot_settings", lang))
settings1, settings2 = st.columns(2)
with settings1:
    book_regions = st.multiselect(tr("book_regions", lang), ["us", "us2", "uk", "eu", "au"], default=["us", "eu", "uk"])
    markets = st.multiselect(tr("markets", lang), ["h2h", "spreads", "totals"], default=["h2h", "spreads", "totals"])
with settings2:
    max_sport_feeds = st.number_input(tr("max_sport_feeds", lang), min_value=1, max_value=100, value=30, step=1)
    max_events_per_feed = st.number_input(tr("max_events", lang), min_value=1, max_value=250, value=25, step=1)

st.subheader(tr("cache_controls", lang))
cache1, cache2, cache3 = st.columns(3)
with cache1:
    snapshot_label = st.text_input(tr("snapshot_label", lang), value="latest")
with cache2:
    output_folder = st.text_input(tr("output_folder", lang), value="data/market_snapshots")
with cache3:
    max_api_calls = st.number_input(tr("max_api_calls", lang), min_value=1, max_value=500, value=25, step=1)
cache_ttl_seconds = st.number_input(tr("cache_ttl", lang), min_value=0, max_value=86400, value=900, step=60)

config = MarketCaptureConfig(
    language=lang,
    odds_api_enabled=bool(odds_api_key.strip()),
    scan_target=scan_target,
    sport_search=sport_search,
    game_filter=game_filter,
    book_regions=book_regions,
    markets=markets,
    max_sport_feeds=int(max_sport_feeds),
    max_events_per_feed=int(max_events_per_feed),
    snapshot_label=snapshot_label,
    output_folder=output_folder,
    max_api_calls=int(max_api_calls),
    cache_ttl_seconds=int(cache_ttl_seconds),
)

if st.button(tr("run_snapshot", lang), type="primary", use_container_width=True):
    st.subheader(tr("decision_output", lang))
    if not config.odds_api_enabled:
        st.warning("Enter The Odds API key." if lang == "en" else "Ingresa la clave de The Odds API.")
    else:
        st.success("Snapshot configuration is ready." if lang == "en" else "La configuración de captura está lista.")
    m1, m2, m3 = st.columns(3)
    m1.metric(tr("markets_selected", lang), len(markets))
    m2.metric(tr("max_sport_feeds", lang), int(max_sport_feeds))
    m3.metric(tr("max_events", lang), int(max_events_per_feed))
    st.subheader(tr("config", lang))
    st.code(json.dumps(asdict(config), indent=2), language="json")
else:
    st.info(tr("enter_fields", lang))

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import streamlit as st

from autonomous_betting_agent.multi_source_fusion import fuse_row
from autonomous_betting_agent.ui_text import LANGUAGES, tr


@dataclass(frozen=True)
class ProConfig:
    language: str
    page: str
    game: str
    sport_search: str
    weather_location: str
    book_regions: list[str]
    markets: list[str]
    odds_enabled: bool
    sports_enabled: bool
    weather_enabled: bool
    ara_memory_enabled: bool


def _pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


def _status(value: bool, lang: str) -> str:
    return tr("enabled", lang) if value else tr("missing", lang)


def _source_inputs(lang: str) -> tuple[str, str, str]:
    st.subheader(tr("api_sources", lang))
    c1, c2, c3 = st.columns(3)
    with c1:
        odds_key = st.text_input(tr("odds_api_key", lang), type="password")
    with c2:
        sports_key = st.text_input(tr("sportsdataio_key", lang), type="password")
    with c3:
        weather_key = st.text_input(tr("weatherapi_key", lang), type="password")
    return odds_key, sports_key, weather_key


def _game_inputs(lang: str, *, default_game: str = "Mexico vs South Korea") -> tuple[str, str, str, list[str], list[str]]:
    st.subheader(tr("game_setup", lang))
    g1, g2 = st.columns(2)
    with g1:
        game = st.text_input(tr("game", lang), value=default_game)
        sport_search = st.text_input(tr("sport_search", lang), value="soccer")
    with g2:
        weather_location = st.text_input(tr("weather_location", lang), value="")
        book_regions = st.multiselect(tr("book_regions", lang), ["us", "us2", "uk", "eu", "au"], default=["us", "eu", "uk"])
    markets = st.multiselect(tr("markets", lang), ["h2h", "spreads", "totals"], default=["h2h", "spreads", "totals"])
    return game, sport_search, weather_location, book_regions, markets


def _show_status(lang: str, odds_key: str, sports_key: str, weather_key: str, ara: bool = False) -> None:
    st.subheader(tr("source_status", lang))
    cols = st.columns(4)
    cols[0].metric("Odds API", _status(bool(odds_key.strip()), lang))
    cols[1].metric("SportsDataIO", _status(bool(sports_key.strip()), lang))
    cols[2].metric("WeatherAPI", _status(bool(weather_key.strip()), lang))
    cols[3].metric("ARA", tr("enabled", lang) if ara else "Off")


def render_pro_predictor(lang: str) -> None:
    st.title("Pro Predictor")
    st.caption(
        "Multi-source all-sports predictor. It combines sportsbook odds, SportsDataIO stats/context, "
        "WeatherAPI conditions, and ARA learning memory through a capped fusion layer."
        if lang == "en"
        else "Predictor multifuente para todos los deportes. Combina cuotas, SportsDataIO, WeatherAPI y memoria ARA con una capa de fusión controlada."
    )
    odds_key, sports_key, weather_key = _source_inputs(lang)
    game, sport_search, weather_location, book_regions, markets = _game_inputs(lang)
    ara_memory = st.toggle("Use ARA learning memory" if lang == "en" else "Usar memoria ARA", value=True)
    with st.expander("Manual signal preview" if lang == "en" else "Vista previa manual", expanded=False):
        p1, p2, p3 = st.columns(3)
        market_prob = p1.number_input("Market probability %", 1.0, 99.0, 56.2, 0.1)
        stats_prob = p1.number_input("Stats probability %", 1.0, 99.0, 58.3, 0.1)
        injury_score = p2.number_input("Injury/lineup score", 0.0, 100.0, 86.0, 1.0)
        weather_score = p3.number_input("Weather score", 0.0, 100.0, 92.0, 1.0)
        memory_roi = p3.number_input("ARA memory ROI %", -100.0, 100.0, 0.0, 0.5)
    _show_status(lang, odds_key, sports_key, weather_key, ara_memory)
    if st.button("Run multi-API Predictor Pro" if lang == "en" else "Ejecutar Predictor Pro multi-API", type="primary", use_container_width=True):
        row = {
            "market_probability": market_prob / 100.0 if odds_key.strip() else "",
            "stats_probability": stats_prob / 100.0 if sports_key.strip() else "",
            "injury_risk_score": injury_score if sports_key.strip() else "",
            "weather_risk_score": weather_score if weather_key.strip() else "",
            "bucket_roi": memory_roi / 100.0 if ara_memory else "",
        }
        fused = fuse_row(row)
        st.subheader("Fusion output" if lang == "en" else "Salida de fusión")
        o1, o2, o3, o4 = st.columns(4)
        o1.metric("Market", _pct(fused.market_probability))
        o2.metric("Final", _pct(fused.final_probability))
        o3.metric("Reliability", f"{fused.reliability_score}/100")
        o4.metric("Confidence", fused.confidence.title())
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Stats", _pct(fused.stats_adjustment))
        a2.metric("Injury", _pct(fused.injury_adjustment))
        a3.metric("Weather", _pct(fused.weather_adjustment))
        a4.metric("ARA", _pct(fused.ara_memory_adjustment))
        config = ProConfig(lang, "pro", game, sport_search, weather_location, book_regions, markets, bool(odds_key.strip()), bool(sports_key.strip()), bool(weather_key.strip()), ara_memory)
        st.code(json.dumps(asdict(config), indent=2), language="json")


def render_market_capture(lang: str) -> None:
    st.title(tr("market_snapshot_title", lang))
    st.caption(tr("market_snapshot_caption", lang))
    odds_key = st.text_input(tr("odds_api_key", lang), type="password")
    game, sport_search, weather_location, book_regions, markets = _game_inputs(lang, default_game="")
    c1, c2, c3 = st.columns(3)
    max_sport_feeds = c1.number_input(tr("max_sport_feeds", lang), 1, 100, 30, 1)
    max_events = c2.number_input(tr("max_events", lang), 1, 250, 25, 1)
    max_api_calls = c3.number_input(tr("max_api_calls", lang), 1, 500, 25, 1)
    snapshot_label = st.text_input(tr("snapshot_label", lang), value="latest")
    output_folder = st.text_input(tr("output_folder", lang), value="data/market_snapshots")
    _show_status(lang, odds_key, "", "")
    if st.button(tr("run_snapshot", lang), type="primary", use_container_width=True):
        if not odds_key.strip():
            st.warning("Enter The Odds API key." if lang == "en" else "Ingresa la clave de The Odds API.")
        st.code(json.dumps({"sport_search": sport_search, "game": game, "regions": book_regions, "markets": markets, "max_sport_feeds": max_sport_feeds, "max_events": max_events, "max_api_calls": max_api_calls, "snapshot_label": snapshot_label, "output_folder": output_folder}, indent=2), language="json")


def render_context_layer(lang: str) -> None:
    st.title(tr("odds_weather_title", lang))
    st.caption(tr("odds_weather_caption", lang))
    odds_key, sports_key, weather_key = _source_inputs(lang)
    game, sport_search, weather_location, book_regions, markets = _game_inputs(lang)
    st.subheader(tr("manual_weather", lang))
    w1, w2, w3 = st.columns(3)
    temp_f = w1.number_input(tr("temperature", lang), -40.0, 130.0, 70.0)
    wind_mph = w2.number_input(tr("wind", lang), 0.0, 100.0, 0.0)
    rain_mm = w3.number_input(tr("rain", lang), 0.0, 200.0, 0.0)
    _show_status(lang, odds_key, sports_key, weather_key)
    if st.button(tr("run_layer", lang), type="primary", use_container_width=True):
        score = 100.0 - (30.0 if wind_mph >= 20 else 12.0 if wind_mph >= 12 else 0.0) - (20.0 if rain_mm >= 5 else 8.0 if rain_mm > 0 else 0.0)
        score = max(0.0, min(100.0, score))
        st.subheader(tr("decision_output", lang))
        d1, d2, d3 = st.columns(3)
        d1.metric(tr("weather_score", lang), f"{score:.1f}/100")
        d2.metric(tr("markets_selected", lang), len(markets))
        d3.metric("Sources", sum([bool(odds_key.strip()), bool(sports_key.strip()), bool(weather_key.strip())]))
        st.code(json.dumps({"game": game, "sport_search": sport_search, "weather_location": weather_location, "regions": book_regions, "markets": markets, "temp_f": temp_f, "wind_mph": wind_mph, "rain_mm": rain_mm}, indent=2), language="json")


st.set_page_config(page_title="Predictor Pro", page_icon="📊", layout="wide")
language_name = st.sidebar.selectbox("Language / Idioma", list(LANGUAGES.keys()), index=0)
lang = LANGUAGES[language_name]
page = st.sidebar.radio("Page" if lang == "en" else "Página", ["Pro Predictor", tr("market_snapshot_title", lang), tr("odds_weather_title", lang)])

if page == "Pro Predictor":
    render_pro_predictor(lang)
elif page == tr("market_snapshot_title", lang):
    render_market_capture(lang)
else:
    render_context_layer(lang)

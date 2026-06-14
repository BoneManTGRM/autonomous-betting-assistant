from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.multi_source_fusion import fuse_row

st.set_page_config(page_title="Pro Predictor", layout="wide")

LANGUAGES = {"English": "en", "Español": "es"}
TEXT = {
    "title": {"en": "Pro Predictor", "es": "Predictor Profesional"},
    "caption": {
        "en": "Multi-source all-sports predictor. It uses sportsbook odds as the base signal, then applies capped adjustments from SportsDataIO, WeatherAPI, and ARA learning memory.",
        "es": "Predictor multifuente para todos los deportes. Usa las cuotas como señal base y aplica ajustes limitados de SportsDataIO, WeatherAPI y memoria ARA.",
    },
    "help": {
        "en": "How to read it: market odds create the base probability. Stats, injuries/lineups, weather/context, and learning memory can move the probability only within capped limits.",
        "es": "Cómo leerlo: las cuotas crean la probabilidad base. Estadísticas, lesiones/alineaciones, clima/contexto y memoria pueden mover la probabilidad solo dentro de límites.",
    },
    "language": {"en": "Language", "es": "Idioma"},
    "api_sources": {"en": "API sources", "es": "Fuentes API"},
    "odds_key": {"en": "Odds API key", "es": "Clave de Odds API"},
    "sports_key": {"en": "SportsDataIO key", "es": "Clave de SportsDataIO"},
    "weather_key": {"en": "WeatherAPI key", "es": "Clave de WeatherAPI"},
    "loaded": {"en": "Loaded from secrets", "es": "Cargada desde secretos"},
    "missing": {"en": "Missing", "es": "Falta"},
    "enabled": {"en": "Enabled", "es": "Activo"},
    "game_setup": {"en": "Game setup", "es": "Configuración del partido"},
    "game": {"en": "Game", "es": "Partido"},
    "scan_target": {"en": "Scan target", "es": "Objetivo de escaneo"},
    "all_sports": {"en": "All sports", "es": "Todos los deportes"},
    "one_league": {"en": "One league/sport", "es": "Una liga/deporte"},
    "one_team": {"en": "One team/player", "es": "Un equipo/jugador"},
    "sport_search": {"en": "Sport/feed search", "es": "Buscar deporte/feed"},
    "team_filter": {"en": "Team/player filter", "es": "Filtro de equipo/jugador"},
    "regions": {"en": "Bookmaker regions", "es": "Regiones de casas"},
    "markets": {"en": "Markets", "es": "Mercados"},
    "controls": {"en": "Predictor controls", "es": "Controles del predictor"},
    "max_feeds": {"en": "Max feeds", "es": "Máximo de feeds"},
    "max_events": {"en": "Max events per feed", "es": "Máximo de eventos por feed"},
    "min_books": {"en": "Minimum books", "es": "Mínimo de casas"},
    "min_reliability": {"en": "Minimum reliability", "es": "Confiabilidad mínima"},
    "manual_preview": {"en": "Manual signal preview", "es": "Vista previa manual"},
    "stats_prob": {"en": "Stats probability %", "es": "Probabilidad por datos %"},
    "injury_score": {"en": "Injury/lineup score", "es": "Puntaje lesión/alineación"},
    "weather_score": {"en": "Weather score", "es": "Puntaje clima"},
    "memory_roi": {"en": "ARA memory ROI %", "es": "ROI memoria ARA %"},
    "memory_upload": {"en": "Upload learning memory CSV", "es": "Subir CSV de memoria"},
    "run": {"en": "Run multi-API Predictor Pro", "es": "Ejecutar Predictor Pro multi-API"},
    "output": {"en": "Fusion output", "es": "Salida de fusión"},
    "table": {"en": "Ranked markets", "es": "Mercados ordenados"},
    "config": {"en": "Run config", "es": "Configuración"},
}


def t(key: str) -> str:
    return TEXT.get(key, {}).get(LANG, TEXT.get(key, {}).get("en", key))


def get_secret(*names: str) -> str:
    for name in names:
        try:
            value = str(st.secrets.get(name, "")).strip()
            if value:
                return value
        except Exception:
            pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def clean(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").replace("_", " ").split())


def similarity(left: str, right: str) -> float:
    left_clean, right_clean = clean(left), clean(right)
    if not left_clean or not right_clean:
        return 0.0
    if left_clean in right_clean:
        return 1.0
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def sport_score(sport: Any, query: str) -> float:
    text = f"{getattr(sport, 'key', '')} {getattr(sport, 'title', '')} {getattr(sport, 'group', '')} {getattr(sport, 'description', '')}"
    if not query or clean(query) == "auto":
        return 0.5
    return similarity(query, text)


def event_match_score(event: Any, query: str) -> float:
    if not query.strip():
        return 1.0
    text = f"{getattr(event, 'home_team', '')} {getattr(event, 'away_team', '')}"
    for outcome in getattr(event, "outcomes", []) or []:
        text += f" {getattr(outcome, 'name', '')}"
    return similarity(query, text)


def top_non_draw(event: Any) -> Any | None:
    outcomes = list(getattr(event, "outcomes", []) or [])
    if not outcomes:
        return None
    return next((outcome for outcome in outcomes if clean(getattr(outcome, "name", "")) != "draw"), outcomes[0])


def pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


@dataclass(frozen=True)
class UIConfig:
    language: str
    odds_api_enabled: bool
    sportsdataio_enabled: bool
    weatherapi_enabled: bool
    game: str
    scan_target: str
    sport_search: str
    team_filter: str
    regions: list[str]
    markets: list[str]
    max_feeds: int
    max_events: int
    min_books: int
    min_reliability: float


language_name = st.selectbox("Language / Idioma", list(LANGUAGES.keys()), index=0)
LANG = LANGUAGES[language_name]

st.title(t("title"))
st.caption(t("caption"))
st.info(t("help"))

st.subheader(t("api_sources"))
saved_odds = get_secret("ODDS_API_KEY", "THE_ODDS_API_KEY")
saved_sports = get_secret("SPORTSDATAIO_API_KEY")
saved_weather = get_secret("WEATHERAPI_KEY", "WEATHER_API_KEY")
api_col1, api_col2, api_col3 = st.columns(3)
with api_col1:
    odds_override = st.text_input(t("odds_key"), type="password", placeholder=t("loaded") if saved_odds else "")
    odds_key = odds_override.strip() or saved_odds
with api_col2:
    sports_override = st.text_input(t("sports_key"), type="password", placeholder=t("loaded") if saved_sports else "")
    sports_key = sports_override.strip() or saved_sports
with api_col3:
    weather_override = st.text_input(t("weather_key"), type="password", placeholder=t("loaded") if saved_weather else "")
    weather_key = weather_override.strip() or saved_weather

status_cols = st.columns(3)
status_cols[0].metric("Odds API", t("enabled") if odds_key else t("missing"))
status_cols[1].metric("SportsDataIO", t("enabled") if sports_key else t("missing"))
status_cols[2].metric("WeatherAPI", t("enabled") if weather_key else t("missing"))

st.subheader(t("game_setup"))
setup1, setup2 = st.columns(2)
with setup1:
    game = st.text_input(t("game"), value="Mexico vs South Korea")
    target_options = [t("all_sports"), t("one_league"), t("one_team")]
    scan_target = st.radio(t("scan_target"), target_options, horizontal=True)
    sport_query = st.text_input(t("sport_search"), value="soccer")
with setup2:
    team_filter = st.text_input(t("team_filter"), value=game if scan_target == t("one_team") else "")
    regions = st.multiselect(t("regions"), ["us", "us2", "uk", "eu", "au"], default=["us", "eu", "uk"])
    markets = st.multiselect(t("markets"), ["h2h", "spreads", "totals"], default=["h2h", "spreads", "totals"])

with st.expander(t("controls"), expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    max_feeds = c1.number_input(t("max_feeds"), min_value=1, max_value=120, value=40, step=1)
    max_events = c2.number_input(t("max_events"), min_value=1, max_value=75, value=25, step=1)
    min_books = c3.number_input(t("min_books"), min_value=1, max_value=25, value=1, step=1)
    min_reliability = c4.slider(t("min_reliability"), min_value=0.0, max_value=100.0, value=0.0, step=1.0)

with st.expander(t("manual_preview"), expanded=False):
    p1, p2, p3 = st.columns(3)
    stats_probability = p1.number_input(t("stats_prob"), min_value=1.0, max_value=99.0, value=58.0, step=0.1)
    injury_score = p2.number_input(t("injury_score"), min_value=0.0, max_value=100.0, value=90.0, step=1.0)
    weather_score = p3.number_input(t("weather_score"), min_value=0.0, max_value=100.0, value=95.0, step=1.0)
    memory_roi = p3.number_input(t("memory_roi"), min_value=-100.0, max_value=100.0, value=0.0, step=0.5)

memory_file = st.file_uploader(t("memory_upload"), type=["csv"])
if memory_file is not None:
    try:
        memory_df = pd.read_csv(memory_file)
        st.success(f"{len(memory_df)} memory rows loaded")
    except Exception as exc:
        st.warning(f"Could not load memory CSV: {exc}")

config = UIConfig(
    language=LANG,
    odds_api_enabled=bool(odds_key),
    sportsdataio_enabled=bool(sports_key),
    weatherapi_enabled=bool(weather_key),
    game=game,
    scan_target=scan_target,
    sport_search=sport_query,
    team_filter=team_filter,
    regions=regions,
    markets=markets,
    max_feeds=int(max_feeds),
    max_events=int(max_events),
    min_books=int(min_books),
    min_reliability=float(min_reliability),
)

if st.button(t("run"), type="primary", use_container_width=True):
    if not odds_key:
        st.warning("Odds API key is required for live market scan." if LANG == "en" else "La clave de Odds API es necesaria para escanear mercados en vivo.")
        preview_row = {
            "market_probability": 0.562,
            "stats_probability": stats_probability / 100.0 if sports_key else "",
            "injury_risk_score": injury_score if sports_key else "",
            "weather_risk_score": weather_score if weather_key else "",
            "bucket_roi": memory_roi / 100.0,
        }
        fused = fuse_row(preview_row)
        st.subheader(t("output"))
        st.write({"market_probability": pct(fused.market_probability), "final_probability": pct(fused.final_probability), "reliability": fused.reliability_score, "confidence": fused.confidence})
        st.code(json.dumps(asdict(config), indent=2), language="json")
        st.stop()

    try:
        sports = list_sports(odds_key, include_all=False)
    except Exception as exc:
        st.error(f"Odds API request failed: {exc}")
        st.stop()

    ranked_sports = sorted(sports, key=lambda sport: sport_score(sport, sport_query), reverse=True)
    selected_sports = ranked_sports[: int(max_feeds)]
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    progress = st.progress(0)
    for index, sport in enumerate(selected_sports):
        try:
            events = scan_market(odds_key, sport.key, regions=",".join(regions), max_events=int(max_events), markets=",".join(markets))
        except Exception as exc:
            skipped.append(f"{getattr(sport, 'title', sport.key)}: {exc}")
            events = []
        for event in events:
            match = event_match_score(event, team_filter)
            if team_filter.strip() and match < 0.85:
                continue
            pick = top_non_draw(event)
            if pick is None:
                continue
            market_probability = float(getattr(pick, "normalized_probability", 0.0) or 0.0)
            books = int(getattr(event, "bookmaker_count", 0) or getattr(pick, "source_count", 0) or 0)
            if books < int(min_books):
                continue
            fusion_input = {
                "market_probability": market_probability,
                "stats_probability": stats_probability / 100.0 if sports_key else "",
                "injury_risk_score": injury_score if sports_key else "",
                "weather_risk_score": weather_score if weather_key else "",
                "bucket_roi": memory_roi / 100.0,
            }
            fused = fuse_row(fusion_input)
            if fused.reliability_score < float(min_reliability):
                continue
            rows.append({
                "event": f"{getattr(event, 'away_team', '')} at {getattr(event, 'home_team', '')}",
                "sport": getattr(event, "sport_title", getattr(sport, "title", "")),
                "start": getattr(event, "commence_time", ""),
                "prediction": getattr(pick, "name", ""),
                "best_price": getattr(pick, "best_price", None) or getattr(pick, "average_price", ""),
                "books": books,
                "market_probability": pct(fused.market_probability),
                "stats_adjustment": pct(fused.stats_adjustment),
                "injury_adjustment": pct(fused.injury_adjustment),
                "weather_adjustment": pct(fused.weather_adjustment),
                "ara_memory_adjustment": pct(fused.ara_memory_adjustment),
                "final_probability": pct(fused.final_probability),
                "reliability_score": fused.reliability_score,
                "confidence": fused.confidence,
                "fusion_reason": fused.fusion_reason,
                "match_score": f"{match:.0%}",
            })
        progress.progress((index + 1) / max(1, len(selected_sports)))
    progress.empty()

    if not rows:
        st.info("No usable markets returned with these filters." if LANG == "en" else "No hubo mercados útiles con estos filtros.")
        if skipped:
            with st.expander("Skipped feeds" if LANG == "en" else "Feeds omitidos"):
                for item in skipped[:50]:
                    st.write(f"- {item}")
        st.stop()

    ranked = sorted(rows, key=lambda row: (row["reliability_score"], row["final_probability"]), reverse=True)
    st.subheader(t("table"))
    st.dataframe(ranked, use_container_width=True, hide_index=True)
    st.download_button("Download CSV" if LANG == "en" else "Descargar CSV", pd.DataFrame(ranked).to_csv(index=False), file_name="pro_predictor_multi_api.csv", mime="text/csv")
    st.subheader(t("config"))
    st.code(json.dumps(asdict(config), indent=2), language="json")
else:
    st.info("Enter API keys and run the multi-source predictor." if LANG == "en" else "Ingresa las claves API y ejecuta el predictor multifuente.")

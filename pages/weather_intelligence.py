import csv
import hashlib
import io
import os
import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from autonomous_betting_agent.weather_context import (
    fetch_weather,
    infer_weather_location_with_confidence,
    is_weather_relevant,
    summary_to_dict,
)
from autonomous_betting_agent.weather_enhancements import (
    effective_risk,
    market_weather_weight,
    nfl_venue_decision,
    weather_action,
)

st.set_page_config(page_title="Weather Intelligence", layout="wide")

language = st.selectbox("Translate page", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Weather Intelligence", "Español": "Inteligencia de Clima"},
    "caption": {
        "English": "WeatherAPI.com-powered betting-weather module. It can check one matchup, use the latest Pro Predictor scan, or scan a CSV. It infers venue cities, caches calls, labels roof/dome context, scores weather risk, and exports a weather-enhanced CSV.",
        "Español": "Módulo de clima con WeatherAPI.com. Puede revisar un partido, usar el último escaneo del Predictor o escanear un CSV. Infiere ciudades, guarda consultas en caché, etiqueta domo/techo, mide riesgo climático y exporta CSV mejorado.",
    },
    "key": {"English": "WeatherAPI key", "Español": "Clave de WeatherAPI"},
    "location": {"English": "Location / stadium city", "Español": "Ubicación / ciudad del estadio"},
    "home": {"English": "Home team / venue side", "Español": "Equipo local / sede"},
    "away": {"English": "Away team", "Español": "Equipo visitante"},
    "sport": {"English": "Sport", "Español": "Deporte"},
    "market": {"English": "Market type, optional", "Español": "Tipo de mercado, opcional"},
    "kickoff": {"English": "Game time ISO, optional", "Español": "Hora del juego ISO, opcional"},
    "run": {"English": "Check weather", "Español": "Revisar clima"},
    "single": {"English": "Single game", "Español": "Un partido"},
    "batch": {"English": "Batch / Pro Predictor scan", "Español": "Lote / escaneo del Predictor"},
    "guide": {"English": "Weather betting guide", "Español": "Guía clima/apuestas"},
    "upload": {"English": "Upload Pro Predictor CSV", "Español": "Subir CSV del Predictor"},
    "use_latest": {"English": "Use latest Pro Predictor scan", "Español": "Usar último escaneo del Predictor"},
    "max_rows": {"English": "Max rows to weather-check", "Español": "Máximo de filas a revisar"},
    "outdoor_only": {"English": "Only check weather-relevant outdoor sports", "Español": "Solo revisar deportes donde el clima importa"},
    "download": {"English": "Download weather-enhanced CSV", "Español": "Descargar CSV con clima"},
    "cache": {"English": "Weather calls cached this session", "Español": "Consultas de clima guardadas en esta sesión"},
    "help": {
        "English": "Set WEATHERAPI_KEY in Streamlit secrets to avoid typing the key. The best workflow is: run Pro Predictor, then come here and click Use latest Pro Predictor scan, or upload a Pro Predictor CSV.",
        "Español": "Guarda WEATHERAPI_KEY en secretos de Streamlit. Flujo recomendado: ejecuta el Predictor, luego aquí presiona Usar último escaneo del Predictor, o sube un CSV del Predictor.",
    },
}


def t(key: str) -> str:
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean_text(value, default="") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    return text if text else default


def find_col(df: pd.DataFrame, names: list[str]):
    lookup = {str(col).strip().lower(): col for col in df.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    for col in df.columns:
        clean_col = str(col).strip().lower()
        if any(name.lower() in clean_col for name in names):
            return col
    return None


def split_event(event: str) -> tuple[str, str]:
    event = clean_text(event)
    if not event:
        return "", ""
    match = re.split(r"\s+(?:at|@|vs\.?|v\.?|versus)\s+", event, maxsplit=1, flags=re.IGNORECASE)
    if len(match) == 2:
        return clean_text(match[0]), clean_text(match[1])
    return "", event


def weather_tier(risk: int) -> str:
    if risk >= 25:
        return "High"
    if risk >= 12:
        return "Medium"
    return "Low"


def market_impact(sport: str, summary, roof_type="outdoor_or_unknown") -> str:
    risk = effective_risk(summary.weather_risk, roof_type)
    sport_text = str(sport or "").lower()
    wind = summary.wind_mph or 0
    gusts = summary.gust_mph or 0
    rain = summary.chance_of_rain or 0
    condition = summary.condition.lower()
    if roof_type == "indoor":
        return "Indoor/roofed venue: weather mostly neutral"
    if roof_type == "retractable_roof":
        return "Roof status matters: verify roof before trusting weather effect"
    if not is_weather_relevant(sport_text):
        return "Weather usually low impact / likely indoor"
    if any(term in sport_text for term in ["baseball", "mlb"]):
        if risk >= 25:
            return "High MLB volatility: totals, delays, pitcher grip, wind/run environment"
        if wind >= 15 or gusts >= 25:
            return "MLB wind angle matters: check park direction before trusting totals"
        if rain >= 50 or "rain" in condition:
            return "MLB rain/delay risk: avoid weak edges"
        return "Normal MLB weather context"
    if any(term in sport_text for term in ["football", "nfl", "ncaaf"]):
        if risk >= 25:
            return "High football weather risk: passing, kicking, turnovers, totals affected"
        if wind >= 15 or gusts >= 25:
            return "Football wind risk: passing/kicking/totals affected"
        if rain >= 50 or "rain" in condition:
            return "Football wet-field risk: higher variance"
        return "Normal football weather context"
    if any(term in sport_text for term in ["soccer", "fifa", "world cup", "veikkausliiga", "dfb", "pokal", "primera"]):
        if risk >= 20:
            return "Soccer weather risk: randomness and draw/under variance can rise"
        if wind >= 15 or rain >= 50:
            return "Soccer conditions watch: wind/rain can reduce clean finishing"
        return "Normal soccer weather context"
    if any(term in sport_text for term in ["tennis", "wta", "atp"]):
        if risk >= 20:
            return "Outdoor tennis risk: wind/rain can affect serve, timing, and delays"
        return "Normal tennis weather context"
    if any(term in sport_text for term in ["golf", "cricket", "odi", "one day", "rugby", "nrl", "afl", "aussie"]):
        if risk >= 20:
            return "Outdoor-weather sport risk: conditions can affect scoring/pace"
        return "Normal outdoor weather context"
    return "Weather context only"


def get_cached_weather(api_key: str, location: str, kickoff: str | None):
    if "ara_weather_cache" not in st.session_state:
        st.session_state.ara_weather_cache = {}
    cache_key = f"{location}|{kickoff or 'current'}"
    if cache_key not in st.session_state.ara_weather_cache:
        st.session_state.ara_weather_cache[cache_key] = fetch_weather(api_key, location, kickoff)
    return st.session_state.ara_weather_cache[cache_key]


def csv_text(df: pd.DataFrame) -> str:
    output = io.StringIO()
    df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return output.getvalue()


def normalize_latest_predictions(predictions) -> pd.DataFrame:
    if not predictions:
        return pd.DataFrame()
    return pd.DataFrame(predictions)


def weather_row_from_prediction(row, event_col, sport_col, start_col, market_col, weather_key, outdoor_only=True):
    base = row.to_dict()
    event = clean_text(row.get(event_col, "")) if event_col else ""
    sport = clean_text(row.get(sport_col, "")) if sport_col else ""
    start = clean_text(row.get(start_col, "")) if start_col else ""
    market = clean_text(row.get(market_col, "")) if market_col else ""
    away, home = split_event(event)
    relevant = is_weather_relevant(sport) if sport else True
    venue = nfl_venue_decision(home, sport)
    guess = infer_weather_location_with_confidence(home, away, sport)
    if venue.location_override:
        guess.location = venue.location_override
        guess.confidence = "exact_home_team_or_venue"
        guess.matched_term = venue.matched_term
        guess.source = "venue_profile"

    base["weather_relevant"] = relevant
    base["weather_event_home"] = home
    base["weather_event_away"] = away
    base["weather_roof_type"] = venue.roof_type
    base["weather_venue_note"] = venue.venue_note

    if outdoor_only and not relevant:
        base.update({
            "weather_location_query": "", "weather_location_confidence": "skipped", "weather_location_matched_term": "", "weather_location_source": "",
            "weather_location": "", "weather_condition": "skipped indoor/low relevance", "weather_temp_f": "", "weather_feelslike_f": "",
            "weather_wind_mph": "", "weather_wind_dir": "", "weather_gust_mph": "", "weather_precip_in": "", "weather_humidity": "",
            "weather_rain_chance": "", "weather_snow_chance": "", "weather_raw_risk": 0, "weather_effective_risk": 0,
            "weather_tier": "Skipped", "weather_action": "Skipped indoor/low weather relevance", "weather_market_weight": "low",
            "weather_notes": "indoor or low weather relevance", "weather_market_impact": "Weather not prioritized for this sport", "weather_error": "",
        })
        return base

    base["weather_location_query"] = guess.location
    base["weather_location_confidence"] = guess.confidence
    base["weather_location_matched_term"] = guess.matched_term
    base["weather_location_source"] = guess.source
    try:
        summary = get_cached_weather(weather_key, guess.location, start or None)
        data = summary_to_dict(summary)
        raw_risk = int(data.get("weather_risk", 0) or 0)
        adjusted_risk = effective_risk(raw_risk, venue.roof_type)
        base.update({
            "weather_location": data.get("location", ""),
            "weather_condition": data.get("condition", ""),
            "weather_temp_f": data.get("temp_f", ""),
            "weather_feelslike_f": data.get("feelslike_f", ""),
            "weather_wind_mph": data.get("wind_mph", ""),
            "weather_wind_dir": data.get("wind_dir", ""),
            "weather_gust_mph": data.get("gust_mph", ""),
            "weather_precip_in": data.get("precip_in", ""),
            "weather_humidity": data.get("humidity", ""),
            "weather_rain_chance": data.get("chance_of_rain", ""),
            "weather_snow_chance": data.get("chance_of_snow", ""),
            "weather_raw_risk": raw_risk,
            "weather_effective_risk": adjusted_risk,
            "weather_tier": weather_tier(adjusted_risk),
            "weather_action": weather_action(summary, sport, venue.roof_type),
            "weather_market_weight": market_weather_weight(sport, market, venue.roof_type),
            "weather_notes": data.get("weather_notes", ""),
            "weather_market_impact": market_impact(sport, summary, venue.roof_type),
            "weather_error": "",
        })
    except Exception as exc:
        base.update({
            "weather_location": guess.location, "weather_condition": "", "weather_temp_f": "", "weather_feelslike_f": "", "weather_wind_mph": "",
            "weather_wind_dir": "", "weather_gust_mph": "", "weather_precip_in": "", "weather_humidity": "", "weather_rain_chance": "",
            "weather_snow_chance": "", "weather_raw_risk": "", "weather_effective_risk": "", "weather_tier": "Error", "weather_action": "WeatherAPI error",
            "weather_market_weight": "", "weather_notes": "", "weather_market_impact": "", "weather_error": str(exc),
        })
    return base


st.title(t("title"))
st.caption(t("caption"))
st.info(t("help"))

try:
    saved_weather_key = str(st.secrets.get("WEATHERAPI_KEY", ""))
except Exception:
    saved_weather_key = os.getenv("WEATHERAPI_KEY", "")

weather_key = st.text_input(t("key"), type="password").strip() or saved_weather_key
if not weather_key:
    st.info("Paste your WeatherAPI key or add WEATHERAPI_KEY to Streamlit secrets." if not IS_ES else "Pega tu clave de WeatherAPI o agrega WEATHERAPI_KEY a los secretos de Streamlit.")
    st.stop()

st.caption(f"{t('cache')}: {len(st.session_state.get('ara_weather_cache', {}))}")

tab_single, tab_batch, tab_guide = st.tabs([t("single"), t("batch"), t("guide")])

with tab_single:
    c1, c2 = st.columns(2)
    home = c1.text_input(t("home"), "Jacksonville Jaguars")
    away = c2.text_input(t("away"), "Cleveland Browns")
    sport = st.text_input(t("sport"), "NFL")
    market = st.text_input(t("market"), "total")
    venue = nfl_venue_decision(home, sport)
    guess = infer_weather_location_with_confidence(home, away, sport)
    if venue.location_override:
        guess.location = venue.location_override
        guess.confidence = "exact_home_team_or_venue"
        guess.matched_term = venue.matched_term
        guess.source = "venue_profile"
    st.caption(f"Inferred location: {guess.location} | confidence: {guess.confidence} | venue: {venue.roof_type} | matched: {guess.matched_term or 'none'}")
    location = st.text_input(t("location"), guess.location)
    kickoff = st.text_input(t("kickoff"), "")

    if st.button(t("run"), type="primary"):
        try:
            summary = get_cached_weather(weather_key, location, kickoff or None)
        except Exception as exc:
            st.error(f"WeatherAPI request failed: {exc}" if not IS_ES else f"Falló la solicitud de WeatherAPI: {exc}")
            st.stop()
        adjusted_risk = effective_risk(summary.weather_risk, venue.roof_type)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Condition" if not IS_ES else "Condición", summary.condition)
        c2.metric("Temp" if not IS_ES else "Temp", "" if summary.temp_f is None else f"{summary.temp_f:.0f}F")
        c3.metric("Wind" if not IS_ES else "Viento", "" if summary.wind_mph is None else f"{summary.wind_mph:.0f} mph {summary.wind_dir}")
        c4.metric("Raw risk" if not IS_ES else "Riesgo bruto", f"{summary.weather_risk}/50")
        c5.metric("Effective risk" if not IS_ES else "Riesgo efectivo", f"{adjusted_risk}/50")
        st.write("Action:" if not IS_ES else "Acción:", weather_action(summary, sport, venue.roof_type))
        st.write("Market weight:" if not IS_ES else "Peso del mercado:", market_weather_weight(sport, market, venue.roof_type))
        st.write("Venue:" if not IS_ES else "Sede:", venue.venue_note)
        st.write("Market impact:" if not IS_ES else "Impacto en mercado:", market_impact(sport, summary, venue.roof_type))
        st.dataframe([summary_to_dict(summary)], use_container_width=True, hide_index=True)
        st.caption(f"Fetched at {datetime.now(timezone.utc).isoformat()}")

with tab_batch:
    latest_predictions = normalize_latest_predictions(st.session_state.get("ara_latest_predictions", []))
    if not latest_predictions.empty:
        st.success(f"Latest Pro Predictor scan available: {len(latest_predictions)} rows")
        if st.button(t("use_latest"), type="secondary"):
            st.session_state.ara_weather_batch_source = latest_predictions
    uploaded = st.file_uploader(t("upload"), type=["csv"])
    max_rows = st.number_input(t("max_rows"), min_value=1, max_value=500, value=50, step=5)
    outdoor_only = st.checkbox(t("outdoor_only"), value=True)

    raw = None
    source_label = ""
    if uploaded is not None:
        try:
            upload_bytes = uploaded.getvalue()
            file_hash = hashlib.sha256(upload_bytes).hexdigest()[:16]
            raw = pd.read_csv(io.BytesIO(upload_bytes))
            source_label = f"upload:{uploaded.name}:{file_hash}"
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}" if not IS_ES else f"No se pudo leer CSV: {exc}")
            st.stop()
    elif isinstance(st.session_state.get("ara_weather_batch_source"), pd.DataFrame):
        raw = st.session_state.ara_weather_batch_source.copy()
        source_label = f"latest_pro_predictor:{len(raw)}"

    if raw is not None and not raw.empty:
        file_key = f"{source_label}:{len(raw)}:{','.join(map(str, raw.columns))}:{int(max_rows)}:{outdoor_only}"
        if st.session_state.get("ara_weather_enhanced_key") != file_key:
            st.session_state.ara_weather_enhanced_csv = pd.DataFrame()
            st.session_state.ara_weather_enhanced_key = file_key
        st.caption(f"Rows loaded: {len(raw)}")
        event_col = find_col(raw, ["event", "evento", "game", "match"])
        sport_col = find_col(raw, ["sport", "deporte", "league", "liga"])
        start_col = find_col(raw, ["start", "commence", "time", "date", "inicio"])
        market_col = find_col(raw, ["market", "market_type", "type", "mercado", "read"])
        if not event_col:
            st.error("Could not find an event/game column." if not IS_ES else "No se encontró columna de evento/partido.")
        elif st.button("Run batch weather scan" if not IS_ES else "Ejecutar escaneo de clima", type="primary"):
            progress = st.progress(0)
            results = []
            scan_df = raw.head(int(max_rows)).copy()
            for index, (_, row) in enumerate(scan_df.iterrows()):
                results.append(weather_row_from_prediction(row, event_col, sport_col, start_col, market_col, weather_key, outdoor_only=outdoor_only))
                progress.progress((index + 1) / max(1, len(scan_df)))
            progress.empty()
            st.session_state.ara_weather_enhanced_csv = pd.DataFrame(results)
            st.session_state.ara_weather_enhanced_key = file_key

    enhanced = st.session_state.get("ara_weather_enhanced_csv")
    if isinstance(enhanced, pd.DataFrame) and not enhanced.empty:
        high = enhanced[enhanced["weather_tier"].astype(str).eq("High")]
        med = enhanced[enhanced["weather_tier"].astype(str).eq("Medium")]
        weak = enhanced[enhanced.get("weather_location_confidence", pd.Series(dtype=str)).astype(str).str.contains("weak", na=False)]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Weather rows" if not IS_ES else "Filas con clima", len(enhanced))
        c2.metric("High risk" if not IS_ES else "Riesgo alto", len(high))
        c3.metric("Medium risk" if not IS_ES else "Riesgo medio", len(med))
        c4.metric("Weak locations" if not IS_ES else "Ubicaciones débiles", len(weak))
        c5.metric(t("cache"), len(st.session_state.get("ara_weather_cache", {})))
        display_cols = [col for col in [
            event_col if raw is not None else None, sport_col if raw is not None else None, start_col if raw is not None else None,
            "weather_location_query", "weather_location_confidence", "weather_roof_type", "weather_venue_note",
            "weather_location", "weather_condition", "weather_temp_f", "weather_wind_mph", "weather_gust_mph",
            "weather_rain_chance", "weather_raw_risk", "weather_effective_risk", "weather_tier", "weather_action",
            "weather_market_weight", "weather_notes", "weather_market_impact", "weather_error",
        ] if col and col in enhanced.columns]
        st.dataframe(enhanced[display_cols], use_container_width=True, hide_index=True)
        st.download_button(t("download"), data=csv_text(enhanced), file_name="weather_enhanced_predictions.csv", mime="text/csv")

with tab_guide:
    st.subheader("How ARA should use weather" if not IS_ES else "Cómo ARA debe usar el clima")
    st.write("MLB totals and NFL/NCAAF totals usually get the highest weather weight. Soccer, outdoor tennis, cricket, rugby, and AFL get medium weight. Indoor/dome venues get reduced weather risk. Retractable-roof games should be manually verified for roof status." if not IS_ES else "Los totales de MLB y NFL/NCAAF suelen tener el mayor peso climático. Fútbol, tenis exterior, cricket, rugby y AFL tienen peso medio. Estadios interiores reducen el riesgo climático. En techos retráctiles conviene verificar estado del techo.")
    st.write("Risk scale uses effective risk after roof/dome adjustment: 0–11 low, 12–24 medium, 25+ high." if not IS_ES else "La escala usa riesgo efectivo después de ajustar por domo/techo: 0–11 bajo, 12–24 medio, 25+ alto.")

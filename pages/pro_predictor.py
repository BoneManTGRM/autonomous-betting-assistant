from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.live_api_context import LiveAPIContextBuilder
from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.multi_source_fusion import fuse_row
from autonomous_betting_agent.target_mode import (
    TargetModePolicy,
    estimated_ev,
    evaluate_target_mode,
    implied_probability,
    price_probability_gap,
)

APP_VERSION = "bilingual-forward-test-v12"
REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_MEMORY_PATH = REPO_ROOT / "data" / "ara_learning_memory.csv"
LEARNED_STATE_PATH = REPO_ROOT / "learned_state.json"

st.set_page_config(page_title="Pro Predictor", layout="wide")
LANG = "es" if st.sidebar.selectbox("Language / Idioma", ["English", "Español"], key="pro_predictor_language") == "Español" else "en"

ES = {
    "Pro Predictor": "Predictor Pro",
    "Multi-source all-sports predictor. Built-in learned memory loads automatically. Upload override is off by default.": "Predictor multifuente para todos los deportes. La memoria aprendida integrada se carga automáticamente. La carga manual está desactivada por defecto.",
    "App version": "Versión de la app",
    "Learned events": "Eventos aprendidos",
    "Raw accuracy": "Precisión bruta",
    "Calibrated accuracy": "Precisión calibrada",
    "Brier after": "Brier después",
    "API sources": "Fuentes API",
    "Odds API key": "Clave de Odds API",
    "SportsDataIO key": "Clave de SportsDataIO",
    "WeatherAPI key": "Clave de WeatherAPI",
    "Enabled": "Activada",
    "Missing": "Falta",
    "Game setup": "Configuración del partido",
    "Game": "Partido",
    "Scan target": "Objetivo del escaneo",
    "All sports": "Todos los deportes",
    "One league/sport": "Una liga/deporte",
    "One team/player": "Un equipo/jugador",
    "Sport/feed search": "Buscar deporte/feed",
    "Team/player filter": "Filtro de equipo/jugador",
    "Bookmaker regions": "Regiones de casas de apuestas",
    "Markets": "Mercados",
    "Predictor controls": "Controles del predictor",
    "Default profile: forward-test 70% scouting. It allows 2 of 3 APIs when SportsDataIO is unsupported or blocked for a sport.": "Perfil por defecto: prueba futura para buscar 70%. Permite 2 de 3 APIs cuando SportsDataIO no es compatible o está bloqueado para un deporte.",
    "Max feeds": "Máximo de feeds",
    "Max events per feed": "Máximo de eventos por feed",
    "Minimum books": "Mínimo de casas",
    "Minimum reliability": "Confiabilidad mínima",
    "Latest event date": "Fecha máxima del evento",
    "70% ±1 Target Mode": "Modo objetivo 70% ±1",
    "Target win probability": "Probabilidad objetivo de ganar",
    "Tolerance ±": "Tolerancia ±",
    "70-mode minimum books": "Mínimo de casas en modo 70",
    "70-mode minimum reliability": "Confiabilidad mínima en modo 70",
    "70-mode market probability floor": "Piso de probabilidad de mercado en modo 70",
    "70-mode minimum EV": "EV mínimo en modo 70",
    "Max price/probability mismatch": "Máxima diferencia precio/probabilidad",
    "70-mode h2h only": "Solo h2h en modo 70",
    "70-mode minimum API coverage": "Cobertura API mínima en modo 70",
    "Require all configured APIs": "Exigir todas las APIs configuradas",
    "Strict official mode values": "Valores para modo oficial estricto",
    "For a strict official run after SportsDataIO works, use: 70-mode reliability 95, API coverage 1.00, and Require all configured APIs ON.": "Para una corrida oficial estricta cuando SportsDataIO funcione, usa confiabilidad 95 en modo 70, cobertura API 1.00 y Exigir todas las APIs ACTIVADO.",
    "Manual signal preview": "Vista previa de señal manual",
    "Manual preview is used only when live API data is unavailable; live scan rows use real API context fields.": "La vista previa manual solo se usa cuando no hay datos API en vivo; las filas del escaneo en vivo usan campos reales de contexto API.",
    "Stats probability %": "Probabilidad estadística %",
    "Injury/lineup score": "Puntaje de lesiones/alineación",
    "Weather score": "Puntaje del clima",
    "Manual ARA memory ROI %": "ROI manual de memoria ARA %",
    "ARA memory": "Memoria ARA",
    "Built-in repo memory loads automatically. Finished-game CSVs belong on the Learning Memory page, not here.": "La memoria integrada del repo se carga automáticamente. Los CSV de partidos terminados van en Memoria de Aprendizaje, no aquí.",
    "Advanced: use uploaded/pasted ARA memory override": "Avanzado: usar memoria ARA subida/pegada",
    "Optional override: upload generated ARA memory CSV only": "Carga opcional: solo CSV de memoria ARA generada",
    "Optional override: paste generated ARA memory CSV": "Pegado opcional: CSV de memoria ARA generada",
    "ARA memory source": "Fuente de memoria ARA",
    "Run multi-API Predictor Pro": "Ejecutar Predictor Pro multi-API",
    "Odds API key is required for live market scan.": "La clave de Odds API es obligatoria para escanear mercados en vivo.",
    "Fusion output": "Resultado de fusión",
    "No usable markets returned with these filters.": "No se encontraron mercados utilizables con estos filtros.",
    "Skipped feeds": "Feeds omitidos",
    "Ranked markets": "Mercados clasificados",
    "70% ±1 Target Picks": "Pronósticos objetivo 70% ±1",
    "Full API rows": "Filas con API completa",
    "Duplicates rejected": "Duplicados rechazados",
    "Download 70% target CSV": "Descargar CSV objetivo 70%",
    "No picks passed 70% ±1 mode. Check rejected rows for the exact blockers.": "Ningún pronóstico pasó el modo 70% ±1. Revisa las filas rechazadas para ver los bloqueos exactos.",
    "Rejected from 70% ±1 Mode": "Rechazados del modo 70% ±1",
    "Download all ranked CSV": "Descargar CSV completo clasificado",
    "Run config": "Configuración de la corrida",
    "Enter API keys and run the multi-source predictor.": "Ingresa las claves API y ejecuta el predictor multifuente.",
}

ES_COLUMNS = {
    "event": "evento", "sport": "deporte", "start": "inicio", "event_date": "fecha_evento", "market_type": "tipo_mercado",
    "prediction": "pronostico", "best_price": "mejor_cuota", "books": "casas", "market_probability": "probabilidad_mercado",
    "final_probability": "probabilidad_final", "final_probability_value": "valor_probabilidad_final", "reliability_score": "puntaje_confiabilidad",
    "confidence": "confianza", "target_70_mode": "modo_objetivo_70", "target_70_rejection_reason": "razon_rechazo_objetivo_70",
    "target_70_quality_score": "puntaje_calidad_objetivo_70", "api_coverage_score": "puntaje_cobertura_api",
    "api_coverage_percent": "porcentaje_cobertura_api", "api_sources_used": "apis_usadas", "api_sources_missing": "apis_faltantes",
    "sportsdataio_status": "estado_sportsdataio", "weatherapi_status": "estado_weatherapi", "estimated_ev_decimal": "ev_estimado_decimal",
}

ES_VALUES = {"HIGH": "ALTA", "MEDIUM": "MEDIA", "LOW": "BAJA", "True": "Verdadero", "False": "Falso", "yes": "sí", "no": "no", "used": "usado", "not_supported_sport": "deporte_no_compatible", "not_configured": "no_configurado"}
ES_PHRASES = {"outside": "fuera de", "market probability below floor": "probabilidad de mercado debajo del piso", "not enough books": "no hay suficientes casas", "reliability below target": "confiabilidad debajo del objetivo", "price/probability mismatch": "desajuste precio/probabilidad", "EV below target": "EV debajo del objetivo", "API coverage below target": "cobertura API debajo del objetivo", "not all configured APIs used": "no se usaron todas las APIs configuradas", "not high confidence": "no es confianza alta", "band": "banda"}


def tt(text: str) -> str:
    return ES.get(text, text) if LANG == "es" else text


def tv(value: Any) -> Any:
    if LANG != "es" or value is None:
        return value
    text = str(value)
    text = ES_VALUES.get(text, text)
    for source, target in ES_PHRASES.items():
        text = text.replace(source, target)
    return text


def report_frame(rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if frame.empty or LANG != "es":
        return frame
    for col in frame.columns:
        if frame[col].dtype == object:
            frame[col] = frame[col].map(tv)
    return frame.rename(columns={col: ES_COLUMNS.get(str(col), str(col)) for col in frame.columns})


@dataclass(frozen=True)
class RunConfig:
    app_version: str
    learned_events_trained: int
    memory_source: str
    memory_rows: int
    memory_signal: float
    odds_api_enabled: bool
    sportsdataio_enabled: bool
    weatherapi_enabled: bool
    scan_target: str
    sport_search: str
    team_filter: str
    regions: list[str]
    markets: list[str]
    max_feeds: int
    max_events: int
    min_books: int
    min_reliability: float
    latest_event_date: str
    target_probability: float
    target_tolerance: float
    target_min_books: int
    target_min_reliability: float
    target_min_market_probability: float
    target_min_ev: float
    target_max_mismatch: float
    target_min_api_coverage: float
    require_all_configured_apis: bool
    target_h2h_only: bool


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


def similarity(left: Any, right: Any) -> float:
    left_clean, right_clean = clean(left), clean(right)
    if not left_clean or not right_clean:
        return 0.0
    if left_clean == right_clean or left_clean in right_clean or right_clean in left_clean:
        return 1.0
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def sport_score(sport: Any, query: str) -> float:
    if not query.strip() or clean(query) == "auto":
        return 0.5
    text = f"{getattr(sport, 'key', '')} {getattr(sport, 'title', '')} {getattr(sport, 'group', '')} {getattr(sport, 'description', '')}"
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


def parse_number(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_learned_state_summary() -> dict[str, Any]:
    try:
        if LEARNED_STATE_PATH.exists():
            payload = json.loads(LEARNED_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass
    return {}


def memory_signal_from_frame(frame: pd.DataFrame | None, manual_roi_percent: float, source_prefix: str) -> tuple[float, str, int]:
    manual_signal = manual_roi_percent / 100.0
    if frame is None or frame.empty:
        return manual_signal, f"{source_prefix}_empty_using_manual", 0
    candidates = ("bucket_roi", "profile_roi", "market_profile_roi", "historical_roi", "ara_memory_adjustment", "memory_adjustment", "learning_adjustment", "smoothed_edge", "roi")
    lowered = {str(col).lower().replace(" ", "_").replace("-", "_"): col for col in frame.columns}
    for candidate in candidates:
        original = lowered.get(candidate)
        if original is None:
            continue
        values: list[float] = []
        weights: list[float] = []
        records_col = lowered.get("records")
        reliability_col = lowered.get("reliability")
        importance_col = lowered.get("importance")
        for idx, item in frame[original].dropna().items():
            parsed = parse_number(item)
            if parsed is None:
                continue
            if abs(parsed) > 1.0:
                parsed /= 100.0
            weight = 1.0
            if records_col is not None:
                record_val = parse_number(frame.loc[idx, records_col])
                if record_val is not None:
                    weight *= max(1.0, min(record_val, 50.0))
            if reliability_col is not None:
                rel_val = parse_number(frame.loc[idx, reliability_col])
                if rel_val is not None:
                    weight *= max(0.1, min(rel_val, 1.0))
            if importance_col is not None:
                imp_val = parse_number(frame.loc[idx, importance_col])
                if imp_val is not None:
                    weight *= max(0.25, min(2.0, 1.0 + imp_val * 5.0))
            values.append(parsed * weight)
            weights.append(weight)
        if values and weights:
            return round(sum(values) / sum(weights), 6), f"{source_prefix}:{original}", len(frame)
    return manual_signal, f"{source_prefix}_no_signal_column_using_manual", len(frame)


def next_sunday(today: date | None = None) -> date:
    base = today or date.today()
    days = (6 - base.weekday()) % 7
    if days == 0:
        days = 7
    return base + timedelta(days=days)


def parse_event_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date()


def api_coverage_fields(api_context: dict[str, Any], *, odds_configured: bool, sports_configured: bool, weather_configured: bool) -> dict[str, Any]:
    configured: list[str] = []
    used: list[str] = []
    if odds_configured:
        configured.append("odds_api")
        if str(api_context.get("odds_api_source_used", "")).lower() == "yes":
            used.append("odds_api")
    if sports_configured:
        configured.append("sportsdataio")
        if str(api_context.get("sportsdataio_source_used", "")).lower() == "yes":
            used.append("sportsdataio")
    if weather_configured:
        configured.append("weatherapi")
        if str(api_context.get("weather_source_used", "")).lower() == "yes":
            used.append("weatherapi")
    configured_count = len(configured)
    used_count = len(used)
    score = 0.0 if configured_count == 0 else round(used_count / configured_count, 6)
    missing = [source for source in configured if source not in used]
    return {"configured_api_sources": ",".join(configured), "api_sources_used": ",".join(used), "api_sources_missing": ",".join(missing), "configured_api_sources_count": configured_count, "api_sources_used_count": used_count, "api_coverage_score": score, "api_coverage_percent": pct(score), "all_configured_apis_used": used_count == configured_count and configured_count > 0}


st.title(tt("Pro Predictor"))
st.caption(tt("Multi-source all-sports predictor. Built-in learned memory loads automatically. Upload override is off by default."))
st.info(f"{tt('App version')}: {APP_VERSION}")

learned_state = load_learned_state_summary()
learned_events = int(learned_state.get("events_trained", 0) or 0)
learned_cols = st.columns(4)
learned_cols[0].metric(tt("Learned events"), learned_events)
learned_cols[1].metric(tt("Raw accuracy"), "" if not learned_state else pct(float(learned_state.get("accuracy_before", 0) or 0)))
learned_cols[2].metric(tt("Calibrated accuracy"), "" if not learned_state else pct(float(learned_state.get("accuracy_after", 0) or 0)))
learned_cols[3].metric(tt("Brier after"), "" if not learned_state else f"{float(learned_state.get('brier_after', 0) or 0):.4f}")

st.subheader(tt("API sources"))
saved_odds = get_secret("ODDS_API_KEY", "THE_ODDS_API_KEY")
saved_sports = get_secret("SPORTSDATAIO_API_KEY")
saved_weather = get_secret("WEATHERAPI_KEY", "WEATHER_API_KEY")
api1, api2, api3 = st.columns(3)
with api1:
    odds_override = st.text_input(tt("Odds API key"), type="password", placeholder="Loaded from secrets" if saved_odds else "")
    odds_key = odds_override.strip() or saved_odds
with api2:
    sports_override = st.text_input(tt("SportsDataIO key"), type="password", placeholder="Loaded from secrets" if saved_sports else "")
    sports_key = sports_override.strip() or saved_sports
with api3:
    weather_override = st.text_input(tt("WeatherAPI key"), type="password", placeholder="Loaded from secrets" if saved_weather else "")
    weather_key = weather_override.strip() or saved_weather
s1, s2, s3 = st.columns(3)
s1.metric("Odds API", tt("Enabled") if odds_key else tt("Missing"))
s2.metric("SportsDataIO", tt("Enabled") if sports_key else tt("Missing"))
s3.metric("WeatherAPI", tt("Enabled") if weather_key else tt("Missing"))

st.subheader(tt("Game setup"))
setup1, setup2 = st.columns(2)
with setup1:
    game = st.text_input(tt("Game"), value="Mexico vs South Korea")
    labels = [tt("All sports"), tt("One league/sport"), tt("One team/player")]
    chosen_scan = st.radio(tt("Scan target"), labels, horizontal=True)
    scan_target = {labels[0]: "All sports", labels[1]: "One league/sport", labels[2]: "One team/player"}[chosen_scan]
    sport_query = st.text_input(tt("Sport/feed search"), value="auto")
with setup2:
    team_filter = st.text_input(tt("Team/player filter"), value=game if scan_target == "One team/player" else "")
    regions = st.multiselect(tt("Bookmaker regions"), ["us", "us2", "uk", "eu", "au"], default=["us", "eu", "uk"])
    markets = st.multiselect(tt("Markets"), ["h2h", "spreads", "totals"], default=["h2h"])

with st.expander(tt("Predictor controls"), expanded=True):
    st.caption(tt("Default profile: forward-test 70% scouting. It allows 2 of 3 APIs when SportsDataIO is unsupported or blocked for a sport."))
    c1, c2, c3, c4, c5 = st.columns(5)
    max_feeds = c1.number_input(tt("Max feeds"), min_value=1, max_value=120, value=50, step=1)
    max_events = c2.number_input(tt("Max events per feed"), min_value=1, max_value=75, value=35, step=1)
    min_books = c3.number_input(tt("Minimum books"), min_value=1, max_value=25, value=4, step=1)
    min_reliability = c4.slider(tt("Minimum reliability"), min_value=0.0, max_value=100.0, value=90.0, step=1.0)
    latest_event_date = c5.date_input(tt("Latest event date"), value=next_sunday())
    st.divider()
    target_70_mode = st.toggle(tt("70% ±1 Target Mode"), value=True)
    t1, t2, t3, t4 = st.columns(4)
    target_probability = t1.number_input(tt("Target win probability"), min_value=0.50, max_value=0.90, value=0.70, step=0.01, format="%.2f")
    target_tolerance = t2.number_input(tt("Tolerance ±"), min_value=0.00, max_value=0.10, value=0.01, step=0.01, format="%.2f")
    target_min_books = t3.number_input(tt("70-mode minimum books"), min_value=1, max_value=25, value=4, step=1)
    target_min_reliability = t4.number_input(tt("70-mode minimum reliability"), min_value=0.0, max_value=100.0, value=90.0, step=1.0)
    q1, q2, q3, q4 = st.columns(4)
    target_min_market_probability = q1.number_input(tt("70-mode market probability floor"), min_value=0.50, max_value=0.90, value=0.62, step=0.01, format="%.2f")
    target_min_ev = q2.number_input(tt("70-mode minimum EV"), min_value=-0.50, max_value=1.00, value=0.00, step=0.01, format="%.2f")
    target_max_mismatch = q3.number_input(tt("Max price/probability mismatch"), min_value=0.01, max_value=0.50, value=0.12, step=0.01, format="%.2f")
    target_h2h_only = q4.toggle(tt("70-mode h2h only"), value=True)
    a1, a2 = st.columns(2)
    target_min_api_coverage = a1.number_input(tt("70-mode minimum API coverage"), min_value=0.0, max_value=1.0, value=0.66, step=0.01, format="%.2f")
    require_all_configured_apis = a2.toggle(tt("Require all configured APIs"), value=False)
    with st.expander(tt("Strict official mode values"), expanded=False):
        st.write(tt("For a strict official run after SportsDataIO works, use: 70-mode reliability 95, API coverage 1.00, and Require all configured APIs ON."))

with st.expander(tt("Manual signal preview"), expanded=False):
    st.caption(tt("Manual preview is used only when live API data is unavailable; live scan rows use real API context fields."))
    p1, p2, p3 = st.columns(3)
    stats_probability = p1.number_input(tt("Stats probability %"), min_value=1.0, max_value=99.0, value=58.0, step=0.1)
    injury_score = p2.number_input(tt("Injury/lineup score"), min_value=0.0, max_value=100.0, value=90.0, step=1.0)
    weather_score = p3.number_input(tt("Weather score"), min_value=0.0, max_value=100.0, value=95.0, step=1.0)
    memory_roi = p3.number_input(tt("Manual ARA memory ROI %"), min_value=-100.0, max_value=100.0, value=0.0, step=0.5)

st.subheader(tt("ARA memory"))
st.caption(tt("Built-in repo memory loads automatically. Finished-game CSVs belong on the Learning Memory page, not here."))
use_memory_override = st.toggle(tt("Advanced: use uploaded/pasted ARA memory override"), value=False)
memory_df: pd.DataFrame | None = None
memory_source_label = "manual_memory_roi"
if use_memory_override:
    memory_upload = st.file_uploader(tt("Optional override: upload generated ARA memory CSV only"), type=["csv"], accept_multiple_files=False, key="optional_memory_override_v12")
    memory_paste = st.text_area(tt("Optional override: paste generated ARA memory CSV"), value="", height=120, key="optional_memory_paste_v12", placeholder="area,area_type,group_value,records,smoothed_edge,reliability")
    if memory_upload is not None:
        try:
            memory_df = pd.read_csv(memory_upload)
            memory_source_label = "uploaded_memory_override"
            st.success(f"{len(memory_df)} ARA memory rows loaded from upload override")
        except Exception as exc:
            st.warning(f"Could not read uploaded memory file; using built-in memory if available. Error: {exc}")
    if memory_df is None and memory_paste.strip():
        try:
            memory_df = pd.read_csv(StringIO(memory_paste.strip()))
            memory_source_label = "pasted_memory_override"
            st.success(f"{len(memory_df)} ARA memory rows loaded from paste override")
        except Exception as exc:
            st.warning(f"Could not read pasted memory CSV; using built-in memory if available. Error: {exc}")
if memory_df is None and REPO_MEMORY_PATH.exists():
    try:
        memory_df = pd.read_csv(REPO_MEMORY_PATH)
        memory_source_label = "built_in_repo_memory"
        st.success(f"{len(memory_df)} ARA memory rows loaded automatically from repo")
    except Exception as exc:
        st.warning(f"Built-in repo memory exists but could not be read. Error: {exc}")
if memory_df is None:
    st.caption("No ARA memory file loaded. Using manual ROI only.")
memory_signal, memory_source, memory_rows = memory_signal_from_frame(memory_df, float(memory_roi), memory_source_label)
st.caption(f"{tt('ARA memory source')}: {memory_source}; rows: {memory_rows}; signal: {memory_signal:.4f}")
if "no_signal_column" in memory_source:
    st.warning("The uploaded memory file did not contain a usable memory signal column. Use the Learning Memory output file named ara_learning_memory.csv, or turn off the override.")

config = RunConfig(APP_VERSION, learned_events, memory_source, memory_rows, memory_signal, bool(odds_key), bool(sports_key), bool(weather_key), scan_target, sport_query, team_filter, regions, markets, int(max_feeds), int(max_events), int(min_books), float(min_reliability), str(latest_event_date), float(target_probability), float(target_tolerance), int(target_min_books), float(target_min_reliability), float(target_min_market_probability), float(target_min_ev), float(target_max_mismatch), float(target_min_api_coverage), bool(require_all_configured_apis), bool(target_h2h_only))
target_policy = TargetModePolicy(target_probability=float(target_probability), tolerance=float(target_tolerance), min_books=int(target_min_books), min_reliability=float(target_min_reliability), min_market_probability=float(target_min_market_probability), min_ev=float(target_min_ev), max_price_probability_gap=float(target_max_mismatch), min_api_coverage_score=float(target_min_api_coverage), require_all_configured_apis=bool(require_all_configured_apis), h2h_only=bool(target_h2h_only))
context_builder = LiveAPIContextBuilder(sportsdataio_key=sports_key, weatherapi_key=weather_key)

if st.button(tt("Run multi-API Predictor Pro"), type="primary", use_container_width=True):
    if not odds_key:
        st.warning(tt("Odds API key is required for live market scan."))
        preview_row = {"market_probability": 0.70, "stats_probability": stats_probability / 100.0, "injury_risk_score": injury_score, "weather_risk_score": weather_score, "bucket_roi": memory_signal}
        fused = fuse_row(preview_row)
        st.subheader(tt("Fusion output"))
        st.write({"market_probability": pct(fused.market_probability), "final_probability": pct(fused.final_probability), "reliability": fused.reliability_score, "confidence": tv(fused.confidence)})
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
    market_param = ",".join(markets or ["h2h"])
    for index, sport in enumerate(selected_sports):
        try:
            events = scan_market(odds_key, sport.key, regions=",".join(regions), max_events=int(max_events), markets=market_param)
        except Exception as exc:
            skipped.append(f"{getattr(sport, 'title', sport.key)}: {exc}")
            events = []
        for event in events:
            event_day = parse_event_date(getattr(event, "commence_time", ""))
            if event_day is None or event_day > latest_event_date:
                continue
            match = event_match_score(event, team_filter)
            if team_filter.strip() and match < 0.85:
                continue
            pick = top_non_draw(event)
            if pick is None:
                continue
            market_probability = float(getattr(pick, "normalized_probability", 0.0) or 0.0)
            best_price = getattr(pick, "best_price", None) or getattr(pick, "average_price", "")
            books = int(getattr(event, "bookmaker_count", 0) or getattr(pick, "source_count", 0) or 0)
            if books < int(min_books):
                continue
            prediction = getattr(pick, "name", "")
            api_context = context_builder.context_for_event(event, pick_name=prediction)
            api_context.update(api_coverage_fields(api_context, odds_configured=bool(odds_key), sports_configured=bool(sports_key), weather_configured=bool(weather_key)))
            fusion_input = {"market_probability": market_probability, "bucket_roi": memory_signal}
            for context_key in ("stats_probability", "injury_risk_score", "weather_risk_score", "weather_flag"):
                if api_context.get(context_key) not in (None, ""):
                    fusion_input[context_key] = api_context[context_key]
            fused = fuse_row(fusion_input)
            if fused.reliability_score < float(min_reliability):
                continue
            final_value = float(fused.final_probability)
            gap_value = price_probability_gap(best_price, market_probability)
            ev_value = estimated_ev(final_value, best_price)
            event_name = f"{getattr(event, 'away_team', '')} at {getattr(event, 'home_team', '')}"
            row = {"event": event_name, "sport": getattr(event, "sport_title", getattr(sport, "title", "")), "start": getattr(event, "commence_time", ""), "event_date": str(event_day), "latest_event_date_filter": str(latest_event_date), "market_type": "h2h", "prediction": prediction, "dedupe_key": clean(f"{event_name} {prediction}"), "duplicate_event_pick": False, "best_price": best_price, "implied_probability_from_price": pct(implied_probability(best_price)), "price_probability_gap": "" if gap_value is None else pct(gap_value), "price_probability_gap_value": gap_value, "price_probability_mismatch": gap_value is None or gap_value > float(target_max_mismatch), "books": books, "market_probability_value": market_probability, "final_probability_value": final_value, "market_probability": pct(fused.market_probability), "stats_adjustment": pct(fused.stats_adjustment), "injury_adjustment": pct(fused.injury_adjustment), "weather_adjustment": pct(fused.weather_adjustment), "ara_memory_adjustment": pct(fused.ara_memory_adjustment), "ara_memory_source": memory_source, "ara_memory_rows": memory_rows, "ara_memory_signal": memory_signal, "final_probability": pct(fused.final_probability), "estimated_ev_value": ev_value, "estimated_ev_decimal": "" if ev_value is None else round(ev_value, 4), "reliability_score": fused.reliability_score, "confidence": fused.confidence, "fusion_reason": fused.fusion_reason, "fusion_warning": fused.fusion_warning, "match_score": f"{match:.0%}"}
            row.update(api_context)
            rows.append(row)
        progress.progress((index + 1) / max(1, len(selected_sports)))
    progress.empty()
    if not rows:
        st.info(tt("No usable markets returned with these filters."))
        if skipped:
            with st.expander(tt("Skipped feeds")):
                for item in skipped[:50]:
                    st.write(f"- {item}")
        st.stop()
    prelim_ranked = sorted(rows, key=lambda row: (row["reliability_score"], row["final_probability_value"], row.get("estimated_ev_value") or -999, row.get("api_coverage_score") or 0), reverse=True)
    seen_keys: set[str] = set()
    for row in prelim_ranked:
        duplicate = row["dedupe_key"] in seen_keys
        row["duplicate_event_pick"] = duplicate
        seen_keys.add(row["dedupe_key"])
        target_result = evaluate_target_mode(row, target_policy)
        row["target_70_quality_score"] = target_result.quality_score
        row["target_70_rejection_reason"] = target_result.rejection_reason
        row["target_70_mode"] = target_result.passed
        row["target_probability_band_low"] = pct(target_result.probability_band_low)
        row["target_probability_band_high"] = pct(target_result.probability_band_high)
    ranked = sorted(prelim_ranked, key=lambda row: (row["target_70_mode"], row["target_70_quality_score"], row.get("api_coverage_score") or 0, row["reliability_score"], row["final_probability_value"]), reverse=True)
    target_rows = [row for row in ranked if row["target_70_mode"]]
    rejected_70 = [row for row in ranked if not row["target_70_mode"]]
    metric_cols = st.columns(6)
    metric_cols[0].metric(tt("Ranked markets"), len(ranked))
    metric_cols[1].metric(tt("70% ±1 Target Picks"), len(target_rows))
    metric_cols[2].metric(tt("Target win probability"), pct(float(target_probability)))
    metric_cols[3].metric(tt("Tolerance ±"), f"±{float(target_tolerance) * 100:.1f}%")
    metric_cols[4].metric(tt("Full API rows"), sum(1 for row in ranked if row.get("all_configured_apis_used") is True))
    metric_cols[5].metric(tt("Duplicates rejected"), sum(1 for row in ranked if row["duplicate_event_pick"]))
    if target_70_mode:
        st.subheader(tt("70% ±1 Target Picks"))
        if target_rows:
            target_report = report_frame(target_rows)
            st.dataframe(target_report, use_container_width=True, hide_index=True)
            st.download_button(tt("Download 70% target CSV"), target_report.to_csv(index=False), file_name="pronosticos_objetivo_70.csv" if LANG == "es" else "pro_predictor_70_target_mode.csv", mime="text/csv")
        else:
            st.info(tt("No picks passed 70% ±1 mode. Check rejected rows for the exact blockers."))
        with st.expander(tt("Rejected from 70% ±1 Mode"), expanded=False):
            st.dataframe(report_frame(rejected_70), use_container_width=True, hide_index=True)
    st.subheader(tt("Ranked markets"))
    ranked_report = report_frame(ranked)
    st.dataframe(ranked_report, use_container_width=True, hide_index=True)
    st.download_button(tt("Download all ranked CSV"), ranked_report.to_csv(index=False), file_name="predictor_pro_multi_api.csv" if LANG == "es" else "pro_predictor_multi_api.csv", mime="text/csv")
    st.subheader(tt("Run config"))
    st.code(json.dumps(asdict(config), indent=2), language="json")
else:
    st.info(tt("Enter API keys and run the multi-source predictor."))

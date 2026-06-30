from __future__ import annotations

import base64
import html
import json
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.fresh_odds_slate_builder import (
    build_slate_rows_from_payload,
    fetch_the_odds_api_payload,
    normalize_the_odds_api_events,
    slate_builder_report_section,
    slate_builder_summary,
)
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="Fresh Odds Slate Builder", layout="wide")
LANG = render_app_sidebar("fresh_odds_slate_builder", language_key="fresh_odds_slate_builder_language", selector="radio")

SPORT_PRESETS = {
    "NBA": {"sport_key": "basketball_nba", "regions": "us", "markets": "h2h,spreads,totals"},
    "WNBA": {"sport_key": "basketball_wnba", "regions": "us", "markets": "h2h,spreads,totals"},
    "MLB": {"sport_key": "baseball_mlb", "regions": "us", "markets": "h2h,spreads,totals"},
    "NFL": {"sport_key": "americanfootball_nfl", "regions": "us", "markets": "h2h,spreads,totals"},
    "NHL": {"sport_key": "icehockey_nhl", "regions": "us", "markets": "h2h,spreads,totals"},
    "EPL Soccer": {"sport_key": "soccer_epl", "regions": "us,uk,eu", "markets": "h2h,spreads,totals"},
}
MARKET_LABELS = {
    "Moneyline / winner": "h2h",
    "Spread / handicap": "spreads",
    "Game total": "totals",
}

TEXT = {
    "en": {
        "title": "Fresh Odds Slate Builder",
        "caption": "Pull a fresh sportsbook slate and send it to Odds Lock Pro. Most of the time, use Pro Predictor first; use this page only when you need a manual fresh-odds pull.",
        "quick_start": "What to do",
        "quick_start_text": "Choose the sport, choose the bet types, press Fetch odds, then send the ready rows to Odds Lock Pro. You normally do not need the raw JSON tools.",
        "fetch": "Simple fresh-odds fetch",
        "sport_preset": "Sport",
        "bet_types": "Bet types to include",
        "fetch_button": "Fetch odds for selected sport",
        "missing_key": "ODDS_API_KEY is not configured in Streamlit secrets. Add it before fetching.",
        "advanced_fetch": "Advanced API settings — usually leave closed",
        "sport_key": "Custom The Odds API sport key",
        "regions": "Regions",
        "markets": "Raw markets string",
        "bookmakers": "Bookmaker filter — optional",
        "manual": "Advanced: import raw API JSON — usually skip",
        "upload": "Upload JSON from an API response",
        "api_name": "API payload type",
        "summary": "Slate summary",
        "rows": "All generated rows",
        "ready": "Ready rows to send forward",
        "missing": "Rows needing review",
        "report": "Technical report — optional",
        "send": "Send ready rows to Odds Lock Pro",
        "sent": "Ready rows were copied to the next-step session for Odds Lock Pro / advisory review.",
        "download": "Download slate CSV",
        "safety_details": "Advanced safety details",
        "safety_warning": "Session-only page. It uses user-triggered API calls only. It does not place bets, mutate proof, run background jobs, expose API keys, or change bankroll/staking.",
        "empty_rows": "No rows yet. Fetch odds or import JSON first.",
    },
    "es": {
        "title": "Constructor de Slate de Odds Frescas",
        "caption": "Consulta una lista fresca de momios y enviala a Odds Lock Pro. Normalmente usa Predictor Pro primero; usa esta pagina solo cuando necesitas consultar momios frescos manualmente.",
        "quick_start": "Qué hacer",
        "quick_start_text": "Elige deporte, elige tipos de apuesta, presiona Consultar momios y envia las filas listas a Odds Lock Pro. Normalmente no necesitas las herramientas JSON.",
        "fetch": "Consulta simple de momios frescos",
        "sport_preset": "Deporte",
        "bet_types": "Tipos de apuesta a incluir",
        "fetch_button": "Consultar momios del deporte seleccionado",
        "missing_key": "ODDS_API_KEY no esta configurada en Streamlit secrets. Agregala antes de consultar.",
        "advanced_fetch": "Configuracion API avanzada — normalmente dejar cerrado",
        "sport_key": "Clave personalizada The Odds API",
        "regions": "Regiones",
        "markets": "Texto raw de mercados",
        "bookmakers": "Filtro bookmaker — opcional",
        "manual": "Avanzado: importar JSON raw — normalmente omitir",
        "upload": "Subir JSON de una respuesta API",
        "api_name": "Tipo de payload API",
        "summary": "Resumen del slate",
        "rows": "Todas las filas generadas",
        "ready": "Filas listas para enviar",
        "missing": "Filas para revisar",
        "report": "Reporte tecnico — opcional",
        "send": "Enviar filas listas a Odds Lock Pro",
        "sent": "Las filas listas fueron copiadas para Odds Lock Pro / revision asesoría.",
        "download": "Descargar CSV de slate",
        "safety_details": "Detalles de seguridad avanzados",
        "safety_warning": "Pagina solo de sesion. Usa llamadas API activadas por el usuario. No apuesta, no muta pruebas, no corre trabajos de fondo, no expone API keys ni cambia bankroll/staking.",
        "empty_rows": "Aun no hay filas. Consulta momios o importa JSON primero.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return localize_dataframe(frame, LANG)


def csv_link(label: str, frame: pd.DataFrame, filename: str) -> None:
    data = base64.b64encode(frame.to_csv(index=False).encode("utf-8")).decode("ascii")
    st.markdown(
        f'<a href="data:text/csv;base64,{data}" download="{html.escape(filename)}" '
        f'style="display:block;text-align:center;background:#ef5350;color:white;'
        f'padding:.75rem 1rem;border-radius:.45rem;text-decoration:none;font-weight:700;">'
        f'{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def show_table(title: str, frame: pd.DataFrame) -> None:
    st.subheader(title)
    if frame.empty:
        st.info(t("empty_rows"))
    else:
        st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


def _load_json_upload(upload: Any) -> Any:
    if upload is None:
        return None
    content = upload.read().decode("utf-8")
    return json.loads(content)


def _selected_markets(labels: list[str]) -> str:
    values = [MARKET_LABELS[label] for label in labels if label in MARKET_LABELS]
    return ",".join(values) or "h2h"


def _current_fetch_settings() -> tuple[str, str, str, str]:
    preset = st.session_state.get("fosb_sport_preset") or "NBA"
    defaults = SPORT_PRESETS.get(str(preset), SPORT_PRESETS["NBA"])
    sport_key = str(st.session_state.get("fosb_custom_sport_key") or defaults["sport_key"]).strip()
    regions = str(st.session_state.get("fosb_regions") or defaults["regions"]).strip()
    markets = str(st.session_state.get("fosb_markets") or defaults["markets"]).strip()
    bookmakers = str(st.session_state.get("fosb_bookmakers") or "").strip()
    return sport_key, regions, markets, bookmakers


st.title(t("title"))
st.caption(t("caption"))
st.info(f"**{t('quick_start')}** — {t('quick_start_text')}")

with st.expander(t("safety_details"), expanded=False):
    st.warning(t("safety_warning"))
    st.json({
        "streamlit_session_only": True,
        "user_triggered_only": True,
        "api_key_exposed": False,
        "database_added": False,
        "scheduled_polling": False,
        "live_betting": False,
        "proof_mutation": False,
    })

rows: list[dict[str, Any]] = []

st.subheader(t("fetch"))
selected_sport = st.selectbox(t("sport_preset"), list(SPORT_PRESETS.keys()), index=0, key="fosb_sport_preset")
selected_markets = st.multiselect(
    t("bet_types"),
    list(MARKET_LABELS.keys()),
    default=["Moneyline / winner", "Spread / handicap", "Game total"],
    key="fosb_market_labels",
)
defaults = SPORT_PRESETS.get(selected_sport, SPORT_PRESETS["NBA"])
st.session_state.setdefault("fosb_custom_sport_key", defaults["sport_key"])
st.session_state.setdefault("fosb_regions", defaults["regions"])
st.session_state["fosb_markets"] = _selected_markets(selected_markets)

with st.expander(t("advanced_fetch"), expanded=False):
    st.text_input(t("sport_key"), value=defaults["sport_key"], key="fosb_custom_sport_key")
    st.text_input(t("regions"), value=defaults["regions"], key="fosb_regions")
    st.text_input(t("markets"), value=_selected_markets(selected_markets), key="fosb_markets")
    st.text_input(t("bookmakers"), value="", key="fosb_bookmakers")

if st.button(t("fetch_button"), type="primary"):
    sport_key, regions, markets, bookmakers = _current_fetch_settings()
    api_key = str(st.secrets.get("ODDS_API_KEY", "") or "")
    if not api_key:
        st.warning(t("missing_key"))
    else:
        try:
            payload = fetch_the_odds_api_payload(
                api_key,
                sport_key=sport_key,
                regions=regions,
                markets=markets,
                bookmakers=bookmakers,
            )
            rows = normalize_the_odds_api_events(payload, sport=sport_key, market=markets.split(",")[0].strip(), bookmaker_filter=bookmakers)
            st.session_state["fresh_odds_slate_builder_rows"] = rows
        except Exception as exc:
            st.error(f"Fresh odds fetch failed: {type(exc).__name__}")

with st.expander(t("manual"), expanded=False):
    st.caption("Use this only when another tool already gave you a raw API response file.")
    api_name = st.selectbox(t("api_name"), ["The Odds API", "SportsDataIO"], index=0)
    upload = st.file_uploader(t("upload"), type=["json"])
    if upload is not None:
        try:
            payload = _load_json_upload(upload)
            rows = build_slate_rows_from_payload(api_name, payload, sport="", market="")
            st.session_state["fresh_odds_slate_builder_rows"] = rows
        except Exception as exc:
            st.error(f"JSON upload failed: {type(exc).__name__}")

rows = rows or st.session_state.get("fresh_odds_slate_builder_rows", []) or []
frame = pd.DataFrame(rows)
summary = slate_builder_summary(rows)

show_table(t("summary"), summary)
show_table(t("rows"), frame)

ready_frame = frame[frame.get("slate_builder_ready_for_advisory_pipeline", pd.Series(dtype=bool)).fillna(False).astype(bool)].copy() if not frame.empty else pd.DataFrame()
missing_frame = frame[frame.get("slate_builder_missing_fields", pd.Series(dtype=str)).fillna("").astype(str) != ""].copy() if not frame.empty else pd.DataFrame()
show_table(t("ready"), ready_frame)
show_table(t("missing"), missing_frame)

if not ready_frame.empty:
    if st.button(t("send"), type="primary"):
        ready_rows = ready_frame.to_dict("records")
        st.session_state["fresh_odds_slate_builder_rows"] = ready_rows
        st.session_state["pro_predictor_latest_rows"] = ready_rows
        st.session_state["odds_lock_pro_candidate_rows"] = ready_rows
        st.success(t("sent"))
    csv_link(t("download"), frame, "fresh_odds_slate_builder.csv")

with st.expander(t("report"), expanded=False):
    st.text_area(t("report"), value=slate_builder_report_section(rows), height=260)

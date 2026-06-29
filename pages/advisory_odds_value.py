from __future__ import annotations

import base64
import html
from typing import Any

import pandas as pd
import streamlit as st

import autonomous_betting_agent.advisory_i18n_phase3e5  # noqa: F401
import autonomous_betting_agent.ui_i18n_phase3e  # noqa: F401
from autonomous_betting_agent.advisory_odds_value_display import (
    ADVISORY_WARNING,
    SAFETY_CONFIRMATION,
    advisory_csv_frame,
    advisory_frame,
    advisory_real_file_diagnostics,
    advisory_report_text,
    advisory_summary_counts,
    blocked_reason_summary,
    duplicate_conflict_summary,
    fresh_slate_readiness_check,
    line_shopping_summary,
    market_completeness_summary,
    playable_table,
    prediction_only_table,
    sportsbook_hold_summary,
    sportsbook_source_summary,
    stale_line_summary,
    validate_advisory_rows,
    watchlist_table,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="Advisory Odds Value", layout="wide")
LANG = render_app_sidebar("advisory_odds_value", language_key="advisory_odds_value_language", selector="radio")

TEXT = {
    "en": {
        "title": "Advisory Odds Value",
        "caption": "Phase 3E.5.6 proof-safe advisory odds readiness, sportsbook source normalization, market completeness diagnostics, and report cleanup.",
        "input": "Input",
        "test_window": "Test Window ID",
        "use_session": "Use latest saved/session rows",
        "upload": "Upload prediction CSV",
        "source": "Input source",
        "none": "none",
        "no_rows": "No rows found. Upload a CSV or run Pro Predictor/Odds Lock Pro first.",
        "safety": "Advisory safety banner",
        "readiness": "Fresh Slate Readiness",
        "readiness_details": "Fresh slate readiness details",
        "source_summary": "Sportsbook Source Summary",
        "market_summary": "Market Completeness Summary",
        "diagnostics": "Why no playable +EV rows?",
        "summary": "Advisory summary",
        "playable": "Playable +EV advisory picks",
        "watchlist": "Watchlist value picks",
        "prediction_only": "Prediction-only rows",
        "prediction_only_note": "These may be good predictions, but the current price does not show playable positive EV.",
        "blocked": "Blocked rows by reason",
        "hold": "Sportsbook hold table",
        "line_shopping": "Best-price line-shopping table",
        "stale": "Stale-line warnings",
        "conflicts": "Duplicate/conflict warnings",
        "validation": "Real-file validation",
        "download": "Download advisory CSV",
        "report": "Copy/paste advisory report",
    },
    "es": {
        "title": "Valor de Odds Asesoría",
        "caption": "Fase 3E.5.6 preparacion, fuentes sportsbook, diagnostico de mercado y reporte asesoría sin tocar prueba.",
        "input": "Entrada",
        "test_window": "ID de ventana de prueba",
        "use_session": "Usar ultimas filas guardadas/sesion",
        "upload": "Subir CSV de predicciones",
        "source": "Fuente de entrada",
        "none": "ninguna",
        "no_rows": "No hay filas. Sube un CSV o ejecuta Predictor Pro/Odds Lock Pro primero.",
        "safety": "Banner de seguridad asesoría",
        "readiness": "Preparacion de slate fresco",
        "readiness_details": "Detalles de preparacion de slate fresco",
        "source_summary": "Resumen de fuente sportsbook",
        "market_summary": "Resumen de mercado completo",
        "diagnostics": "Por que no hay filas +EV jugables?",
        "summary": "Resumen asesoría",
        "playable": "Picks asesoría jugables +EV",
        "watchlist": "Picks de valor en watchlist",
        "prediction_only": "Filas solo prediccion",
        "prediction_only_note": "Pueden ser buenas predicciones, pero el precio actual no muestra EV positivo jugable.",
        "blocked": "Filas bloqueadas por razon",
        "hold": "Tabla hold de sportsbook",
        "line_shopping": "Tabla mejor precio line-shopping",
        "stale": "Alertas de linea vieja",
        "conflicts": "Alertas duplicado/conflicto",
        "validation": "Validacion de archivo real",
        "download": "Descargar CSV asesoría",
        "report": "Reporte asesoría para copiar/pegar",
    },
}

HANDOFF_KEYS = [
    "pro_predictor_latest_rows",
    "pro_predictor_high_confidence_rows",
    "ara_latest_predictions",
    "what_are_the_odds_latest_rows",
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
]


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


def rows_from_sources(workspace_id: str) -> tuple[str, list[dict[str, Any]]]:
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return key, [dict(row) for row in rows if isinstance(row, dict)]
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    if rows:
        st.session_state[key] = rows
        return f"local:{key}", rows
    return "", []


def read_inputs(workspace_id: str) -> tuple[str, pd.DataFrame]:
    label, rows = rows_from_sources(workspace_id)
    use_session = st.checkbox(t("use_session"), value=bool(rows))
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    if use_session and rows:
        frames.append(pd.DataFrame(rows))
        names.append(label or "saved_rows")
    uploads = st.file_uploader(t("upload"), type=["csv"], accept_multiple_files=True)
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame["source_file"] = upload.name
                frames.append(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f"{upload.name}: {exc}")
    if not frames:
        return "", pd.DataFrame()
    return ", ".join(names), pd.concat(frames, ignore_index=True, sort=False)


def show_table(title: str, frame: pd.DataFrame, *, note: str | None = None) -> None:
    st.subheader(title)
    if note:
        st.caption(note)
    if frame.empty:
        st.info("No rows.")
    else:
        st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


st.title(t("title"))
st.caption(t("caption"))

with st.expander(t("input"), expanded=True):
    workspace_input = st.text_input(t("test_window"), value=st.session_state.get("aba_test_window_id", "test_01"))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state["aba_test_window_id"] = workspace_id
    source_name, raw = read_inputs(workspace_id)

if raw.empty:
    st.caption(f"{t('source')}: {t('none')}")
    st.warning(t("no_rows"))
    st.stop()

normalized = normalize_frame(raw)
advisory = advisory_frame(normalized)
validation = validate_advisory_rows(normalized)
counts = advisory_summary_counts(advisory)
readiness = fresh_slate_readiness_check(advisory)
diagnostics = advisory_real_file_diagnostics(advisory)

st.caption(f"{t('source')}: {source_name or t('none')}")
st.subheader(t("safety"))
st.warning(ADVISORY_WARNING)
st.info(SAFETY_CONFIRMATION)
st.json({
    "advisory_only": True,
    "proof_preserving": True,
    "live_application": "OFF",
    "applied_live_count": 0,
    "does_not_feed_official_locks": True,
})

st.subheader(t("readiness"))
score_col, status_col = st.columns(2)
score_col.metric("Readiness score", f"{readiness['readiness_score']}/100")
status_col.metric("Readiness status", readiness["readiness_status"])
st.info(readiness.get("recommended_next_action", "Review advisory tables."))
with st.expander(t("readiness_details"), expanded=True):
    st.json(readiness)

show_table(t("source_summary"), sportsbook_source_summary(advisory))
show_table(t("market_summary"), market_completeness_summary(advisory))

st.subheader(t("diagnostics"))
if diagnostics.get("show_no_playable_warning"):
    st.warning(diagnostics.get("explanation", "No playable advisory rows were found."))
st.info(diagnostics.get("recommended_next_action", "Review advisory tables before manual promotion in a later phase."))
st.json(diagnostics)

st.subheader(t("summary"))
metric_cols = st.columns(9)
metric_cols[0].metric("Rows", counts["total_advisory_rows"])
metric_cols[1].metric("Playable +EV", counts["PLAYABLE_PLUS_EV"])
metric_cols[2].metric("Watchlist", counts["WATCHLIST_VALUE"])
metric_cols[3].metric("Prediction-only", counts["PREDICTION_ONLY_NOT_PLUS_EV"])
metric_cols[4].metric("Blocked", counts["blocked_rows"])
metric_cols[5].metric("Stale", counts["stale_rows"])
metric_cols[6].metric("Unknown", counts["unknown_freshness_rows"])
metric_cols[7].metric("Complete", counts["complete_markets"])
metric_cols[8].metric("Conflicts", counts["duplicate_conflict_rows"])

show_table(t("playable"), playable_table(advisory))
show_table(t("watchlist"), watchlist_table(advisory))
show_table(t("prediction_only"), prediction_only_table(advisory), note=t("prediction_only_note"))
show_table(t("blocked"), blocked_reason_summary(advisory))
show_table(t("hold"), sportsbook_hold_summary(advisory))
show_table(t("line_shopping"), line_shopping_summary(advisory))
show_table(t("stale"), stale_line_summary(advisory))
show_table(t("conflicts"), duplicate_conflict_summary(advisory))

st.subheader(t("validation"))
st.json(validation)

csv_link(t("download"), advisory_csv_frame(advisory), f"advisory_odds_value_{workspace_id}.csv")
st.subheader(t("report"))
st.text_area(t("report"), value=advisory_report_text(advisory), height=360)

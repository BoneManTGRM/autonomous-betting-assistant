import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.dashboard_data_service import build_dashboard_data
from autonomous_betting_agent.dashboard_ledger_bridge import build_dashboard_from_ledger, dashboard_source_summary
from autonomous_betting_agent.dashboard_ui import (
    dashboard_json_text,
    dashboard_tables,
    operator_status_cards,
    operator_traffic_light_statuses,
    primary_kpi_cards,
    proof_grade_label,
    proof_performance_cards,
    status_cards,
)
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.proof_center_control_service import get_dashboard_readiness, get_ledger_health, get_proof_center_status
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Dashboard", layout="wide")
LANG = render_app_sidebar("dashboard", language_key="dashboard_language", selector="radio")

TEXT = {
    "en": {
        "title": "Dashboard Operator View",
        "caption": "Ledger-backed metrics are proof-grade. Session/upload fallback metrics are temporary and not final proof.",
        "workspace": "Client / Workspace ID",
        "input": "Input rows",
        "source": "Source",
        "selected_source": "Selected source",
        "upload": "Upload fallback dashboard CSV rows",
        "learning_upload": "Optional learning CSV rows",
        "settings": "Bankroll / API settings",
        "bankroll": "Current bankroll",
        "unit_size": "Unit size",
        "max_daily_fraction": "Max daily exposure fraction",
        "api_used": "API calls used",
        "api_limit": "API call limit",
        "operator_status": "Operator Status Strip",
        "traffic_lights": "Operator Traffic-Light Status",
        "primary_kpis": "Primary KPI Cards",
        "proof_performance": "Proof / Performance",
        "top_picks": "Top +EV Picks",
        "top_picks_empty": "No playable positive-EV picks found.",
        "risk_bankroll": "Risk / Bankroll",
        "system_health": "System Health",
        "status_cards": "Legacy Status Cards",
        "odds_lock": "Odds Lock Pro Summary",
        "bankroll_summary": "Bankroll Summary",
        "proof_summary": "Proof Summary",
        "clv_summary": "CLV Summary",
        "roi_summary": "ROI Summary",
        "recent_activity": "Recent Activity",
        "upcoming_events": "Upcoming Events",
        "json_contract": "Full Dashboard JSON Contract",
        "download_json": "Download dashboard JSON",
        "empty": "No ledger, session, or uploaded rows found. Dashboard is showing the empty safety path.",
        "ledger_warning": "Dashboard is not powered by durable ledger rows. Metrics are provisional fallback values, not final proof.",
        "ledger_empty": "Ledger rows are empty for this workspace.",
        "integrity_warning": "Ledger integrity is not PASS.",
        "api_high": "API usage is high.",
        "risk_high": "Bankroll risk is high.",
        "proof_grade": "Proof grade",
        "provisional": "Provisional / fallback metrics",
        "ledger_backed": "Ledger-backed proof metrics",
        "raw_diagnostics": "Raw diagnostics",
        "sync_summary": "Dashboard source summary",
        "dashboard_readiness": "Dashboard readiness",
        "ledger_health": "Ledger health",
        "proof_center_status": "Proof Center status",
    },
    "es": {
        "title": "Vista Operadora del Dashboard",
        "caption": "Las métricas respaldadas por ledger son de grado prueba. Las métricas de sesión/subida son temporales y no son prueba final.",
        "workspace": "ID de cliente / workspace",
        "input": "Filas de entrada",
        "source": "Fuente",
        "selected_source": "Fuente seleccionada",
        "upload": "Subir CSV fallback para dashboard",
        "learning_upload": "CSV opcional de aprendizaje",
        "settings": "Bankroll / uso de API",
        "bankroll": "Bankroll actual",
        "unit_size": "Tamaño de unidad",
        "max_daily_fraction": "Exposición diaria máxima",
        "api_used": "Llamadas API usadas",
        "api_limit": "Límite de llamadas API",
        "operator_status": "Barra de estado operadora",
        "traffic_lights": "Estado tipo semáforo",
        "primary_kpis": "Tarjetas KPI principales",
        "proof_performance": "Prueba / rendimiento",
        "top_picks": "Top picks +EV",
        "top_picks_empty": "No se encontraron picks jugables con EV positivo.",
        "risk_bankroll": "Riesgo / bankroll",
        "system_health": "Salud del sistema",
        "status_cards": "Tarjetas de estado anteriores",
        "odds_lock": "Resumen Odds Lock Pro",
        "bankroll_summary": "Resumen de bankroll",
        "proof_summary": "Resumen de prueba",
        "clv_summary": "Resumen CLV",
        "roi_summary": "Resumen ROI",
        "recent_activity": "Actividad reciente",
        "upcoming_events": "Próximos eventos",
        "json_contract": "Contrato JSON completo del dashboard",
        "download_json": "Descargar JSON del dashboard",
        "empty": "No se encontraron filas de ledger, sesión o CSV subido. El dashboard muestra la ruta segura vacía.",
        "ledger_warning": "El dashboard no está usando filas durables de ledger. Las métricas son provisionales, no prueba final.",
        "ledger_empty": "No hay filas de ledger para este workspace.",
        "integrity_warning": "La integridad del ledger no está en PASS.",
        "api_high": "El uso de API es alto.",
        "risk_high": "El riesgo de bankroll es alto.",
        "proof_grade": "Grado de prueba",
        "provisional": "Métricas provisionales / fallback",
        "ledger_backed": "Métricas de prueba respaldadas por ledger",
        "raw_diagnostics": "Diagnósticos crudos",
        "sync_summary": "Resumen de fuente del dashboard",
        "dashboard_readiness": "Preparación del dashboard",
        "ledger_health": "Salud del ledger",
        "proof_center_status": "Estado del Proof Center",
    },
}

HANDOFF_KEYS = (
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "pro_predictor_high_confidence_rows",
    "pro_predictor_latest_rows",
    "what_are_the_odds_latest_rows",
    "ara_latest_predictions",
)

LEARNING_SESSION_KEYS = (
    "learning_memory_rows",
    "ara_learning_memory_rows",
    "learning_latest_rows",
    "learn_memory_latest_rows",
    "graded_upload_rows",
)

API_USAGE_KEYS = (
    "dashboard_api_usage",
    "aba_api_usage",
    "api_usage_summary",
    "odds_api_usage",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ARA_MEMORY_PATH = REPO_ROOT / "data" / "ara_learning_memory.csv"


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _read_uploads(uploads: list[Any] | None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for upload in uploads or []:
        try:
            frame = pd.read_csv(upload)
            frame["source_file"] = getattr(upload, "name", "uploaded.csv")
            frames.append(frame)
        except Exception as exc:
            st.warning(f"{getattr(upload, 'name', 'upload')}: {exc}")
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _session_rows(keys: tuple[str, ...]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for key in keys:
        rows = st.session_state.get(key)
        if rows is None:
            continue
        if isinstance(rows, pd.DataFrame):
            frame = rows.copy(deep=True)
        else:
            try:
                frame = pd.DataFrame(list(rows))
            except Exception:
                continue
        if not frame.empty:
            frame["source_key"] = key
            frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _load_saved_fallback_rows(workspace_id: str) -> pd.DataFrame:
    try:
        key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
        frame = pd.DataFrame(rows)
        if rows and not frame.empty:
            frame["source_key"] = f"saved:{key}"
            return frame
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def _load_learning_rows(uploaded_learning: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    session_frame = _session_rows(LEARNING_SESSION_KEYS)
    if not session_frame.empty:
        frames.append(session_frame)
    if ARA_MEMORY_PATH.exists():
        try:
            file_frame = pd.read_csv(ARA_MEMORY_PATH)
            file_frame["source_key"] = "data/ara_learning_memory.csv"
            frames.append(file_frame)
        except Exception:
            pass
    if uploaded_learning is not None and not uploaded_learning.empty:
        frames.append(uploaded_learning)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _api_usage_from_state(manual_used: int, manual_limit: int) -> dict[str, Any]:
    for key in API_USAGE_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, Mapping):
            data = dict(value)
            data.setdefault("sources", [key])
            return data
    return {"used_calls": manual_used, "call_limit": manual_limit, "sources": ["manual_dashboard_input"]}


def _compat_dashboard_data(rows: pd.DataFrame, learning_rows: pd.DataFrame, api_usage: Mapping[str, Any], bankroll: float, unit_size: float, max_daily_fraction: float) -> dict[str, Any]:
    return build_dashboard_data(rows, learning_rows=learning_rows, api_usage=api_usage, bankroll=bankroll, unit_size=unit_size, max_daily_fraction=max_daily_fraction)


def _render_card_rows(cards: list[dict[str, Any]], columns_per_row: int = 4) -> None:
    for start in range(0, len(cards), columns_per_row):
        columns = st.columns(columns_per_row)
        for column, card in zip(columns, cards[start:start + columns_per_row]):
            column.metric(card.get("label", ""), card.get("value", ""), help=card.get("help") or None)


def _render_table(title: str, frame: pd.DataFrame, empty_message: str = "No rows available.") -> None:
    st.subheader(title)
    if frame.empty:
        st.info(empty_message)
    else:
        with st.expander(title, expanded=True):
            st.dataframe(frame, use_container_width=True, hide_index=True)


def _render_summary_table(title: str, frame: pd.DataFrame) -> None:
    st.markdown(f"**{title}**")
    if frame.empty:
        st.info("No rows available.")
    else:
        st.dataframe(frame, use_container_width=True, hide_index=True)


def _warning_messages(sync_summary: Mapping[str, Any], ledger_health: Mapping[str, Any], dashboard: Mapping[str, Any], traffic: Mapping[str, str]) -> list[str]:
    messages: list[str] = []
    selected = str(sync_summary.get("selected_source") or "empty")
    if selected != "ledger":
        messages.append(t("ledger_warning"))
    if int(sync_summary.get("ledger_rows", 0) or 0) == 0:
        messages.append(t("ledger_empty"))
    if str(ledger_health.get("status") or "PASS").upper() != "PASS":
        messages.append(t("integrity_warning"))
    if traffic.get("api_status") == "API HIGH USAGE":
        messages.append(t("api_high"))
    if traffic.get("risk_status") == "RISK HIGH":
        messages.append(t("risk_high"))
    if not dashboard.get("events_scanned"):
        messages.append(t("empty"))
    return messages


st.title(t("title"))
st.caption(t("caption"))

with st.expander(t("input"), expanded=True):
    workspace_input = st.text_input(t("workspace"), value=st.session_state.get("aba_test_window_id", "test_01"))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state["aba_test_window_id"] = workspace_id
    dashboard_uploads = st.file_uploader(t("upload"), type=["csv"], accept_multiple_files=True, key="dashboard_rows_upload")
    uploaded_rows = _read_uploads(dashboard_uploads)
    saved_fallback_rows = _load_saved_fallback_rows(workspace_id)
    uploaded_frames = [frame for frame in (saved_fallback_rows, uploaded_rows) if frame is not None and not frame.empty]
    learning_uploads = st.file_uploader(t("learning_upload"), type=["csv"], accept_multiple_files=True, key="dashboard_learning_upload")
    uploaded_learning_rows = _read_uploads(learning_uploads)
    learning_rows = _load_learning_rows(uploaded_learning_rows)

with st.expander(t("settings"), expanded=False):
    bankroll = st.number_input(t("bankroll"), min_value=0.0, value=float(st.session_state.get("dashboard_bankroll", 1000.0)), step=50.0)
    unit_size = st.number_input(t("unit_size"), min_value=0.0, value=float(st.session_state.get("dashboard_unit_size", 10.0)), step=1.0)
    max_daily_fraction = st.number_input(t("max_daily_fraction"), min_value=0.0, max_value=1.0, value=float(st.session_state.get("dashboard_max_daily_fraction", 0.05)), step=0.01)
    api_used = st.number_input(t("api_used"), min_value=0, value=int(st.session_state.get("dashboard_api_used", 0)), step=100)
    api_limit = st.number_input(t("api_limit"), min_value=0, value=int(st.session_state.get("dashboard_api_limit", 0)), step=100)

api_usage = _api_usage_from_state(int(api_used), int(api_limit))
source_summary = dashboard_source_summary(workspace_id, session_state=st.session_state, uploaded_frames=uploaded_frames)
dashboard = build_dashboard_from_ledger(
    workspace_id,
    session_state=st.session_state,
    uploaded_frames=uploaded_frames,
    learning_rows=learning_rows,
    api_usage=api_usage,
    bankroll=float(bankroll),
    unit_size=float(unit_size),
    max_daily_fraction=float(max_daily_fraction),
)
if source_summary.get("selected_source") == "empty":
    dashboard = _compat_dashboard_data(pd.DataFrame(), learning_rows, api_usage, float(bankroll), float(unit_size), float(max_daily_fraction))
    dashboard["sync_summary"] = source_summary
else:
    dashboard.setdefault("sync_summary", source_summary)

proof_status = get_proof_center_status(workspace_id)
ledger_health = get_ledger_health(workspace_id)
dashboard_readiness = get_dashboard_readiness(workspace_id)
sync_summary = dashboard.get("sync_summary") or source_summary
traffic = operator_traffic_light_statuses(dashboard, proof_status, ledger_health, dashboard_readiness, sync_summary)
tables = dashboard_tables(dashboard)

st.subheader(t("operator_status"))
st.caption(f"{t('selected_source')}: {sync_summary.get('selected_source', 'empty')} | {t('proof_grade')}: {proof_grade_label(sync_summary.get('selected_source', 'empty'))}")
_render_card_rows(operator_status_cards(dashboard, proof_status, ledger_health, dashboard_readiness, sync_summary), columns_per_row=4)

st.subheader(t("traffic_lights"))
traffic_columns = st.columns(5)
for column, key in zip(traffic_columns, ["proof_status", "ledger_status", "dashboard_source_status", "risk_status", "api_status"]):
    column.metric(key.replace("_", " ").title(), traffic.get(key, ""))

for message in _warning_messages(sync_summary, ledger_health, dashboard, traffic):
    st.warning(message)

st.subheader(t("primary_kpis"))
if sync_summary.get("selected_source") == "ledger":
    st.caption(t("ledger_backed"))
else:
    st.caption(t("provisional"))
_render_card_rows(primary_kpi_cards(dashboard, proof_status), columns_per_row=5)

st.subheader(t("proof_performance"))
_render_card_rows(proof_performance_cards(proof_status), columns_per_row=4)

_render_table(t("top_picks"), tables["top_positive_ev_picks"], empty_message=t("top_picks_empty"))

risk_col, health_col = st.columns(2)
with risk_col:
    st.subheader(t("risk_bankroll"))
    _render_summary_table(t("bankroll_summary"), tables["bankroll_summary"])
    st.metric("Recommended Bets", dashboard.get("positive_ev_picks", 0))
    st.metric("Estimated Exposure", (dashboard.get("bankroll_summary") or {}).get("daily_exposure", "N/A"))
    st.metric("Bankroll Risk Status", traffic.get("risk_status", ""))
with health_col:
    st.subheader(t("system_health"))
    st.metric("API Status", traffic.get("api_status", ""))
    st.metric("Learning Rows Scanned", dashboard.get("learning_rows_scanned", 0))
    _render_summary_table(t("odds_lock"), tables["odds_lock_summary"])

proof_col, clv_col, roi_col = st.columns(3)
with proof_col:
    _render_summary_table(t("proof_summary"), tables["proof_summary"])
with clv_col:
    _render_summary_table(t("clv_summary"), tables["clv_summary"])
with roi_col:
    _render_summary_table(t("roi_summary"), tables["roi_summary"])

activity_col, event_col = st.columns(2)
with activity_col:
    _render_table(t("recent_activity"), tables["recent_activity"])
with event_col:
    _render_table(t("upcoming_events"), tables["upcoming_events"])

with st.expander(t("status_cards"), expanded=False):
    _render_card_rows(status_cards(dashboard), columns_per_row=5)

json_text = dashboard_json_text(dashboard)
with st.expander(t("raw_diagnostics"), expanded=False):
    st.subheader(t("sync_summary"))
    st.json(sync_summary)
    st.subheader(t("dashboard_readiness"))
    st.json(dashboard_readiness)
    st.subheader(t("ledger_health"))
    st.json(ledger_health)
    st.subheader(t("proof_center_status"))
    st.json(proof_status)
    st.subheader(t("json_contract"))
    st.code(json_text, language="json")
    st.download_button(
        t("download_json"),
        data=json_text.encode("utf-8"),
        file_name=f"dashboard_{workspace_id}.json",
        mime="application/json",
        key="dashboard_json_download",
    )

from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.subscriber_ledger import (
    build_subscriber_ledger_reports_from_text,
    export_ledger_checks_csv,
    export_ledger_manifest_json,
    export_ledger_rows_csv,
    export_market_type_performance_csv,
    export_mistake_patterns_csv,
    export_sport_performance_csv,
    export_sportsbook_performance_csv,
    export_subscriber_ledger_json,
    export_subscriber_summaries_csv,
)

st.set_page_config(page_title="Subscriber Ledger", layout="wide")
LANG = render_app_sidebar("subscriber_ledger", language_key="subscriber_ledger_language")
REPORT_KEY = "subscriber_ledger_report"
PAGE_CONTRACT_FIELDS = ("schema_version", "workspace_id", "ledger_run_id", "ledger_hash", "mode", "ledger_status", "ledger_row_count", "subscriber_count", "unique_event_count", "global_summary", "subscriber_summaries", "ledger_rows", "sport_performance", "market_type_performance", "sportsbook_performance", "mistake_patterns", "ledger_checks", "safety_gates", "preview_only", "files_written", "live_changes")

TEXT = {
    "en": {
        "title": "Subscriber Ledger", "caption": "Builds subscriber-level result reports from the current proof ledger.", "help": "Usually no CSV paste is needed. This page will use the current saved proof ledger for the selected workspace. Manual CSV input is under Advanced.",
        "workspace_id": "Workspace ID", "source": "Automatic source check", "run": "Build ledger reports", "advanced": "Advanced manual input", "ledger_csv": "Manual subscriber ledger CSV", "summary": "Summary", "global": "Global results", "subs": "Subscriber summaries", "rows": "Ledger rows", "sports": "Sport performance", "markets": "Market performance", "books": "Sportsbook performance", "patterns": "Mistake patterns", "checks": "Checks", "safety": "Safety details", "download_json": "Download ledger JSON", "download_rows": "Download rows CSV", "download_subs": "Download summaries CSV", "download_sports": "Download sport CSV", "download_markets": "Download market CSV", "download_books": "Download sportsbook CSV", "download_patterns": "Download patterns CSV", "download_checks": "Download checks CSV", "download_manifest": "Download manifest JSON", "preview_only": "Preview only", "no_files": "No files written.", "no_live": "No live changes.", "no_report": "Build ledger reports to view outputs.", "no_source": "No saved ledger rows found for this workspace. Lock picks in Odds Lock Pro first.",
    },
    "es": {
        "title": "Ledger de Subscribers", "caption": "Construye reportes por subscriber desde el ledger de prueba actual.", "help": "Normalmente no necesitas pegar CSV. Esta página usa el proof ledger guardado del workspace. Entrada manual está en Avanzado.",
        "workspace_id": "ID de workspace", "source": "Revisión de fuente automática", "run": "Construir reportes ledger", "advanced": "Entrada manual avanzada", "ledger_csv": "CSV manual de subscriber ledger", "summary": "Resumen", "global": "Resultados globales", "subs": "Resumen por subscriber", "rows": "Filas ledger", "sports": "Performance por deporte", "markets": "Performance por mercado", "books": "Performance por sportsbook", "patterns": "Patrones de errores", "checks": "Checks", "safety": "Detalles de seguridad", "download_json": "Descargar JSON ledger", "download_rows": "Descargar CSV filas", "download_subs": "Descargar CSV summaries", "download_sports": "Descargar CSV deportes", "download_markets": "Descargar CSV mercados", "download_books": "Descargar CSV books", "download_patterns": "Descargar CSV patrones", "download_checks": "Descargar CSV checks", "download_manifest": "Descargar JSON manifest", "preview_only": "Solo preview", "no_files": "No escribe archivos.", "no_live": "No hace cambios live.", "no_report": "Construye reportes ledger para ver outputs.", "no_source": "No hay filas guardadas para este workspace. Bloquea picks en Odds Lock Pro primero.",
    },
}

def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)

def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "ledger"

def _auto_ledger_csv(workspace_id: str) -> tuple[str, int]:
    try:
        frame = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    except Exception:
        frame = pd.DataFrame()
    if frame.empty:
        return "", 0
    return frame.to_csv(index=False), int(len(frame))

st.title(t("title")); st.caption(t("caption")); st.info(t("help"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="subscriber_ledger_workspace_id"))
auto_csv, auto_rows = _auto_ledger_csv(workspace_id)
st.subheader(t("source")); cols = st.columns(2); cols[0].metric("saved ledger rows", auto_rows); cols[1].metric("workspace", workspace_id)
if auto_rows <= 0: st.warning(t("no_source"))
with st.expander(t("advanced"), expanded=False):
    ledger_csv = st.text_area(t("ledger_csv"), value=auto_csv, key="subscriber_ledger_csv", height=220)
if st.button(t("run"), key="subscriber_ledger_run", type="primary"):
    st.session_state[REPORT_KEY] = build_subscriber_ledger_reports_from_text(workspace_id, ledger_csv or auto_csv)
report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report")); st.stop()
metrics = st.columns(7); metrics[0].metric("status", report.get("ledger_status", "")); metrics[1].metric("rows", report.get("ledger_row_count", 0)); metrics[2].metric("subscribers", report.get("subscriber_count", 0)); metrics[3].metric("unique events", report.get("unique_event_count", 0)); metrics[4].metric("ROI", report.get("global_summary", {}).get("roi")); metrics[5].metric("win rate", report.get("global_summary", {}).get("win_rate_ex_push_cancel")); metrics[6].metric("fail", report.get("fail_count", 0))
tabs = st.tabs([t("summary"), t("global"), t("subs"), t("rows"), t("sports"), t("markets"), t("books"), t("patterns"), t("checks")])
with tabs[0]: st.json({field: report.get(field) for field in PAGE_CONTRACT_FIELDS})
with tabs[1]: st.json(report.get("global_summary") or {})
with tabs[2]: st.dataframe(pd.DataFrame(report.get("subscriber_summaries") or []), use_container_width=True, hide_index=True)
with tabs[3]: st.dataframe(pd.DataFrame(report.get("ledger_rows") or []), use_container_width=True, hide_index=True)
with tabs[4]: st.dataframe(pd.DataFrame(report.get("sport_performance") or []), use_container_width=True, hide_index=True)
with tabs[5]: st.dataframe(pd.DataFrame(report.get("market_type_performance") or []), use_container_width=True, hide_index=True)
with tabs[6]: st.dataframe(pd.DataFrame(report.get("sportsbook_performance") or []), use_container_width=True, hide_index=True)
with tabs[7]: st.dataframe(pd.DataFrame(report.get("mistake_patterns") or []), use_container_width=True, hide_index=True)
with tabs[8]: st.dataframe(pd.DataFrame(report.get("ledger_checks") or []), use_container_width=True, hide_index=True)
with st.expander(t("safety"), expanded=False): st.json(report.get("safety_gates") or {})
suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('ledger_hash'))}"
st.download_button(t("download_json"), export_subscriber_ledger_json(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_{suffix}.json", mime="application/json", key=f"subscriber_ledger_json_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_rows"), export_ledger_rows_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_rows_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_rows_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_subs"), export_subscriber_summaries_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_summaries_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_subs_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_sports"), export_sport_performance_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_sports_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_sports_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_markets"), export_market_type_performance_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_markets_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_markets_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_books"), export_sportsbook_performance_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_books_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_books_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_patterns"), export_mistake_patterns_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_patterns_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_patterns_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_checks"), export_ledger_checks_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_checks_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_checks_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_manifest"), export_ledger_manifest_json(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_manifest_{suffix}.json", mime="application/json", key=f"subscriber_ledger_manifest_{safe_text(report.get('ledger_hash'))}")

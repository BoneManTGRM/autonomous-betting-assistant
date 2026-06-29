from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.update_flow_service import (
    build_dashboard_update_payload,
    build_update_flow_report,
    export_proposed_updates_csv,
    export_update_flow_json,
    parse_update_csv_text,
)

st.set_page_config(page_title="Update Flow Control", layout="wide")
LANG = render_app_sidebar("update_flow_control", language_key="update_flow_control_language")

REPORT_KEY = "update_flow_control_report"

TEXT = {
    "en": {
        "title": "Update Flow Control",
        "caption": "Preview-only control layer for source confirmations, value snapshots, review flags, dashboard metrics, and clean exports.",
        "workspace_id": "Workspace ID",
        "locked_csv": "Locked rows CSV",
        "confirmation_csv": "Confirmation CSV",
        "value_csv": "Value CSV",
        "run_flow": "Run full update preview",
        "ready": "READY TO EXPORT",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_change": "NO RECORD CHANGE PERFORMED",
        "frozen_logic": "FROZEN SELECTION LOGIC",
        "report_summary": "Report summary",
        "dashboard_payload": "Dashboard update payload",
        "proposed_exports": "Proposed exports",
        "download_json": "Download clean JSON report",
        "download_csv": "Download proposed updates CSV",
        "no_report": "Run full update preview to view report details.",
    },
    "es": {
        "title": "Control de Flujo de Actualización",
        "caption": "Capa solo vista previa para confirmaciones, snapshots de valor, flags de revisión, métricas de dashboard y exportes limpios.",
        "workspace_id": "ID de workspace",
        "locked_csv": "CSV de filas bloqueadas",
        "confirmation_csv": "CSV de confirmación",
        "value_csv": "CSV de valor",
        "run_flow": "Ejecutar vista previa de actualización completa",
        "ready": "READY TO EXPORT",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_change": "NO RECORD CHANGE PERFORMED",
        "frozen_logic": "FROZEN SELECTION LOGIC",
        "report_summary": "Resumen del reporte",
        "dashboard_payload": "Payload de actualización del dashboard",
        "proposed_exports": "Exportes propuestos",
        "download_json": "Descargar reporte JSON limpio",
        "download_csv": "Descargar CSV de actualizaciones propuestas",
        "no_report": "Ejecuta la vista previa de actualización completa para ver detalles.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="update_flow_workspace_id"))

locked_csv = st.text_area(t("locked_csv"), value="", key="update_flow_locked_csv", height=120)
confirmation_csv = st.text_area(t("confirmation_csv"), value="", key="update_flow_confirmation_csv", height=120)
value_csv = st.text_area(t("value_csv"), value="", key="update_flow_value_csv", height=120)

if st.button(t("run_flow"), key="update_flow_run"):
    st.session_state[REPORT_KEY] = build_update_flow_report(
        workspace_id,
        parse_update_csv_text(locked_csv),
        parse_update_csv_text(confirmation_csv),
        parse_update_csv_text(value_csv),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

status_key = "ready" if report.get("status") == "READY TO EXPORT" else "review" if report.get("status") == "REVIEW REQUIRED" else "empty"
st.write({t(status_key): True, t("preview_only"): bool(report.get("preview_only")), t("no_change"): int(report.get("changed_records") or 0) == 0, t("frozen_logic"): bool(report.get("frozen_selection_logic"))})

metrics = st.columns(6)
metrics[0].metric("status", safe_text(report.get("status")))
metrics[1].metric("row_count", report.get("row_count", 0))
metrics[2].metric("unique_events", report.get("unique_events", 0))
metrics[3].metric("ready_count", report.get("ready_count", 0))
metrics[4].metric("review_count", report.get("review_count", 0))
metrics[5].metric("hash", _fragment(report.get("reconciliation_report_hash")))

st.markdown(f"### {t('report_summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "status": report.get("status"),
    "safe_to_export": report.get("safe_to_export"),
    "preview_only": report.get("preview_only"),
    "changed_records": report.get("changed_records"),
    "frozen_selection_logic": report.get("frozen_selection_logic"),
    "row_count": report.get("row_count"),
    "unique_events": report.get("unique_events"),
    "duplicate_row_count": report.get("duplicate_row_count"),
    "confirmation_payload_count": report.get("confirmation_payload_count"),
    "value_payload_count": report.get("value_payload_count"),
    "ready_count": report.get("ready_count"),
    "review_count": report.get("review_count"),
    "reconciliation_report_hash": report.get("reconciliation_report_hash"),
})

st.markdown(f"### {t('dashboard_payload')}")
st.json(build_dashboard_update_payload(report))

st.markdown(f"### {t('proposed_exports')}")
st.dataframe(pd.DataFrame(report.get("proposed_exports") or []), use_container_width=True, hide_index=True)

st.download_button(
    t("download_json"),
    export_update_flow_json(report).encode("utf-8"),
    file_name=f"aba_update_flow_{safe_text(report.get('workspace_id'))}_{_fragment(report.get('reconciliation_report_hash'))}.json",
    mime="application/json",
    key=f"update_flow_json_{safe_text(report.get('reconciliation_report_hash'))}",
)
st.download_button(
    t("download_csv"),
    export_proposed_updates_csv(report).encode("utf-8"),
    file_name=f"aba_update_flow_updates_{safe_text(report.get('workspace_id'))}_{_fragment(report.get('reconciliation_report_hash'))}.csv",
    mime="text/csv",
    key=f"update_flow_csv_{safe_text(report.get('reconciliation_report_hash'))}",
)

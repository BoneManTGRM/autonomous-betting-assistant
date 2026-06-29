from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.data_reconciliation_preview_service import (
    build_data_reconciliation_report,
    export_data_reconciliation_report_json,
    validate_data_reconciliation_report,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Data Reconciliation Preview", layout="wide")
LANG = render_app_sidebar("data_reconciliation_preview", language_key="data_reconciliation_language")

LOCKED_ROWS_KEY = "data_reconciliation_locked_rows"
CONFIRMATION_ROWS_KEY = "data_reconciliation_confirmation_rows"
VALUE_ROWS_KEY = "data_reconciliation_value_rows"
REPORT_KEY = "data_reconciliation_report"

TEXT = {
    "en": {
        "title": "Data Reconciliation Preview",
        "caption": "Read-only preview for source confirmations, value snapshots, review flags, and frozen selection logic.",
        "workspace_id": "Workspace ID",
        "event": "Event",
        "sport": "Sport",
        "market_type": "Market type",
        "selection": "Selection",
        "source": "Source",
        "primary_value": "Primary value",
        "secondary_value": "Secondary value",
        "confidence": "Confidence",
        "original_value": "Original value",
        "latest_value": "Latest value",
        "add_locked_row": "Add locked row",
        "add_confirmation": "Add confirmation payload",
        "add_value": "Add value payload",
        "clear_preview": "Clear preview",
        "run_preview": "Run reconciliation preview",
        "row_ready": "Locked row added in memory. No files were written.",
        "confirmation_ready": "Confirmation payload added in memory. No files were written.",
        "value_ready": "Value payload added in memory. No files were written.",
        "cleared": "Preview cleared in memory.",
        "report_ready": "Reconciliation report generated in memory. No files were written.",
        "reconciled": "RECONCILED",
        "review_required": "REVIEW REQUIRED",
        "missing_confirmation": "MISSING CONFIRMATION",
        "no_rows": "NO ROWS",
        "frozen_logic": "FROZEN SELECTION LOGIC",
        "locked_rows": "Locked rows",
        "confirmation_rows": "Confirmation payloads",
        "value_rows": "Value payloads",
        "reconciliation_rows": "Reconciliation rows",
        "report_summary": "Report summary",
        "validation": "Report validation",
        "download_report": "Download reconciliation JSON",
        "no_report": "Run reconciliation preview to view report details.",
    },
    "es": {
        "title": "Vista Previa de Reconciliación de Datos",
        "caption": "Vista solo lectura para confirmaciones de fuente, snapshots de valor, flags de revisión y lógica congelada de selección.",
        "workspace_id": "ID de workspace",
        "event": "Evento",
        "sport": "Sport",
        "market_type": "Tipo de mercado",
        "selection": "Selección",
        "source": "Fuente",
        "primary_value": "Valor primario",
        "secondary_value": "Valor secundario",
        "confidence": "Confianza",
        "original_value": "Valor original",
        "latest_value": "Valor más reciente",
        "add_locked_row": "Agregar fila bloqueada",
        "add_confirmation": "Agregar payload de confirmación",
        "add_value": "Agregar payload de valor",
        "clear_preview": "Limpiar vista previa",
        "run_preview": "Ejecutar vista de reconciliación",
        "row_ready": "Fila bloqueada agregada en memoria. No se escribieron archivos.",
        "confirmation_ready": "Payload de confirmación agregado en memoria. No se escribieron archivos.",
        "value_ready": "Payload de valor agregado en memoria. No se escribieron archivos.",
        "cleared": "Vista previa limpiada en memoria.",
        "report_ready": "Reporte de reconciliación generado en memoria. No se escribieron archivos.",
        "reconciled": "RECONCILED",
        "review_required": "REVIEW REQUIRED",
        "missing_confirmation": "MISSING CONFIRMATION",
        "no_rows": "NO ROWS",
        "frozen_logic": "FROZEN SELECTION LOGIC",
        "locked_rows": "Filas bloqueadas",
        "confirmation_rows": "Payloads de confirmación",
        "value_rows": "Payloads de valor",
        "reconciliation_rows": "Filas de reconciliación",
        "report_summary": "Resumen del reporte",
        "validation": "Validación del reporte",
        "download_report": "Descargar JSON de reconciliación",
        "no_report": "Ejecuta la vista de reconciliación para ver detalles del reporte.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _hash_fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _report_filename(report: dict) -> str:
    return f"aba_data_reconciliation_{safe_text(report.get('workspace_id'))}_{_hash_fragment(report.get('report_hash'))}.json"


def _rows(key: str) -> list[dict]:
    return list(st.session_state.get(key) or [])


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="reconciliation_workspace_id"))

cols = st.columns(5)
sport = cols[0].text_input(t("sport"), value="tennis", key="reconciliation_sport")
event = cols[1].text_input(t("event"), value="", key="reconciliation_event")
market_type = cols[2].selectbox(t("market_type"), ("moneyline", "spread", "total", "custom_market"), index=0, key="reconciliation_market_type")
selection = cols[3].text_input(t("selection"), value="", key="reconciliation_selection")
source = cols[4].text_input(t("source"), value="manual_preview", key="reconciliation_source")

cols2 = st.columns(5)
primary_value = cols2[0].number_input(t("primary_value"), min_value=0.0, value=0.0, step=1.0, key="reconciliation_primary_value")
secondary_value = cols2[1].number_input(t("secondary_value"), min_value=0.0, value=0.0, step=1.0, key="reconciliation_secondary_value")
confidence = cols2[2].number_input(t("confidence"), min_value=0.0, max_value=1.0, value=1.0, step=0.05, key="reconciliation_confidence")
original_value = cols2[3].number_input(t("original_value"), min_value=0.0, value=2.0, step=0.01, key="reconciliation_original_value")
latest_value = cols2[4].number_input(t("latest_value"), min_value=0.0, value=2.0, step=0.01, key="reconciliation_latest_value")

buttons = st.columns(5)
base_payload = {"workspace_id": workspace_id, "sport": sport, "event": event or "manual_event", "market_type": market_type, "selection": selection or "manual_selection", "event_start_utc": "manual_preview", "source": source or "manual_preview"}
with buttons[0]:
    if st.button(t("add_locked_row"), key="reconciliation_add_locked_row"):
        rows = _rows(LOCKED_ROWS_KEY)
        rows.append({**base_payload, "proof_id": f"preview_{len(rows) + 1}"})
        st.session_state[LOCKED_ROWS_KEY] = rows
        st.info(t("row_ready"))
with buttons[1]:
    if st.button(t("add_confirmation"), key="reconciliation_add_confirmation"):
        confirmations = _rows(CONFIRMATION_ROWS_KEY)
        confirmations.append({**base_payload, "primary_value": float(primary_value), "secondary_value": float(secondary_value), "confidence": float(confidence)})
        st.session_state[CONFIRMATION_ROWS_KEY] = confirmations
        st.info(t("confirmation_ready"))
with buttons[2]:
    if st.button(t("add_value"), key="reconciliation_add_value"):
        values = _rows(VALUE_ROWS_KEY)
        values.append({**base_payload, "original_value": float(original_value), "latest_value": float(latest_value)})
        st.session_state[VALUE_ROWS_KEY] = values
        st.info(t("value_ready"))
with buttons[3]:
    if st.button(t("clear_preview"), key="reconciliation_clear_preview"):
        st.session_state[LOCKED_ROWS_KEY] = []
        st.session_state[CONFIRMATION_ROWS_KEY] = []
        st.session_state[VALUE_ROWS_KEY] = []
        st.session_state[REPORT_KEY] = {}
        st.info(t("cleared"))
with buttons[4]:
    if st.button(t("run_preview"), key="reconciliation_run_preview"):
        report = build_data_reconciliation_report(workspace_id, _rows(LOCKED_ROWS_KEY), _rows(CONFIRMATION_ROWS_KEY), _rows(VALUE_ROWS_KEY))
        st.session_state[REPORT_KEY] = report
        st.info(t("report_ready"))

st.markdown(f"### {t('locked_rows')}")
st.dataframe(pd.DataFrame(_rows(LOCKED_ROWS_KEY)), use_container_width=True, hide_index=True)
st.markdown(f"### {t('confirmation_rows')}")
st.dataframe(pd.DataFrame(_rows(CONFIRMATION_ROWS_KEY)), use_container_width=True, hide_index=True)
st.markdown(f"### {t('value_rows')}")
st.dataframe(pd.DataFrame(_rows(VALUE_ROWS_KEY)), use_container_width=True, hide_index=True)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

validation = validate_data_reconciliation_report(report)
status_key = "reconciled" if report.get("status") == "RECONCILED" else "missing_confirmation" if report.get("status") == "MISSING CONFIRMATION" else "review_required" if report.get("status") == "REVIEW REQUIRED" else "no_rows"
st.write({t(status_key): True, t("frozen_logic"): bool(report.get("frozen_selection_logic"))})

metrics = st.columns(6)
metrics[0].metric("status", safe_text(report.get("status")))
metrics[1].metric("row_count", report.get("row_count", 0))
metrics[2].metric("unique_events", report.get("unique_events", 0))
metrics[3].metric("reconciled_count", report.get("reconciled_count", 0))
metrics[4].metric("review_count", report.get("review_count", 0))
metrics[5].metric("report_hash", safe_text(report.get("report_hash"))[:18])

st.markdown(f"### {t('report_summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "report_id": report.get("report_id"),
    "report_hash": report.get("report_hash"),
    "status": report.get("status"),
    "overall_passed": report.get("overall_passed"),
    "row_count": report.get("row_count"),
    "unique_events": report.get("unique_events"),
    "duplicate_row_count": report.get("duplicate_row_count"),
    "confirmation_payload_count": report.get("confirmation_payload_count"),
    "value_payload_count": report.get("value_payload_count"),
    "reconciled_count": report.get("reconciled_count"),
    "review_count": report.get("review_count"),
    "frozen_selection_logic": report.get("frozen_selection_logic"),
    "warning_count": len(report.get("warnings") or []),
    "error_count": len(report.get("errors") or []),
})
st.markdown(f"### {t('reconciliation_rows')}")
st.dataframe(pd.DataFrame(report.get("reconciliation_rows") or []), use_container_width=True, hide_index=True)

with st.expander(t("validation"), expanded=False):
    st.json(validation)

st.download_button(
    t("download_report"),
    export_data_reconciliation_report_json(report, public_safe=True).encode("utf-8"),
    file_name=_report_filename(report),
    mime="application/json",
    key=f"data_reconciliation_report_json_{safe_text(report.get('report_hash'))}",
)

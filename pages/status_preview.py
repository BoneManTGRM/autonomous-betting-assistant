from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.status_preview_service import build_status_preview_report, export_status_preview_report_json, validate_status_preview_report

st.set_page_config(page_title="Status Preview", layout="wide")
LANG = render_app_sidebar("status_preview", language_key="status_preview_language")

RECORDS_KEY = "status_preview_records"
MARKERS_KEY = "status_preview_markers"
SNAPSHOTS_KEY = "status_preview_snapshots"
REPORT_KEY = "status_preview_report"

TEXT = {
    "en": {
        "title": "Status Preview",
        "caption": "Read-only preview for source markers, value snapshots, review flags, and locked logic.",
        "workspace_id": "Workspace ID",
        "category": "Category",
        "name": "Name",
        "source": "Source",
        "primary": "Primary",
        "secondary": "Secondary",
        "confidence": "Confidence",
        "start_value": "Start value",
        "latest_value": "Latest value",
        "add_record": "Add record",
        "add_marker": "Add marker",
        "add_snapshot": "Add snapshot",
        "clear_preview": "Clear preview",
        "run_preview": "Run preview",
        "ready": "READY",
        "review": "REVIEW",
        "missing": "MISSING",
        "empty": "EMPTY",
        "locked_logic": "LOCKED LOGIC",
        "records": "Records",
        "markers": "Markers",
        "snapshots": "Snapshots",
        "status_rows": "Status rows",
        "report_summary": "Report summary",
        "validation": "Report validation",
        "download_report": "Download status preview JSON",
        "no_report": "Run preview to view report details.",
    },
    "es": {
        "title": "Vista Previa de Estado",
        "caption": "Vista solo lectura para marcadores de fuente, snapshots de valor, flags de revisión y lógica bloqueada.",
        "workspace_id": "ID de workspace",
        "category": "Categoría",
        "name": "Nombre",
        "source": "Fuente",
        "primary": "Primario",
        "secondary": "Secundario",
        "confidence": "Confianza",
        "start_value": "Valor inicial",
        "latest_value": "Valor reciente",
        "add_record": "Agregar registro",
        "add_marker": "Agregar marcador",
        "add_snapshot": "Agregar snapshot",
        "clear_preview": "Limpiar vista previa",
        "run_preview": "Ejecutar vista previa",
        "ready": "READY",
        "review": "REVIEW",
        "missing": "MISSING",
        "empty": "EMPTY",
        "locked_logic": "LOCKED LOGIC",
        "records": "Registros",
        "markers": "Marcadores",
        "snapshots": "Snapshots",
        "status_rows": "Filas de estado",
        "report_summary": "Resumen del reporte",
        "validation": "Validación del reporte",
        "download_report": "Descargar JSON de vista previa",
        "no_report": "Ejecuta la vista previa para ver detalles del reporte.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _filename(report: dict) -> str:
    return f"aba_status_preview_{safe_text(report.get('workspace_id'))}_{_fragment(report.get('report_hash'))}.json"


def _rows(key: str) -> list[dict]:
    return list(st.session_state.get(key) or [])


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="status_preview_workspace_id"))

cols = st.columns(5)
category = cols[0].text_input(t("category"), value="group", key="status_preview_category")
name = cols[1].text_input(t("name"), value="", key="status_preview_name")
source = cols[2].text_input(t("source"), value="manual", key="status_preview_source")
primary = cols[3].number_input(t("primary"), min_value=0.0, value=0.0, step=1.0, key="status_preview_primary")
secondary = cols[4].number_input(t("secondary"), min_value=0.0, value=0.0, step=1.0, key="status_preview_secondary")

cols2 = st.columns(3)
confidence = cols2[0].number_input(t("confidence"), min_value=0.0, max_value=1.0, value=1.0, step=0.05, key="status_preview_confidence")
start_value = cols2[1].number_input(t("start_value"), min_value=0.0, value=1.0, step=0.01, key="status_preview_start_value")
latest_value = cols2[2].number_input(t("latest_value"), min_value=0.0, value=1.0, step=0.01, key="status_preview_latest_value")

buttons = st.columns(4)
base = {"workspace_id": workspace_id, "category": category, "name": name or "manual_record", "time": "manual", "source": source or "manual"}
with buttons[0]:
    if st.button(t("add_record"), key="status_preview_add_record"):
        rows = _rows(RECORDS_KEY)
        rows.append({**base, "record_id": f"preview_{len(rows) + 1}"})
        st.session_state[RECORDS_KEY] = rows
with buttons[1]:
    if st.button(t("add_marker"), key="status_preview_add_marker"):
        rows = _rows(MARKERS_KEY)
        rows.append({**base, "primary": float(primary), "secondary": float(secondary), "confidence": float(confidence)})
        st.session_state[MARKERS_KEY] = rows
with buttons[2]:
    if st.button(t("add_snapshot"), key="status_preview_add_snapshot"):
        rows = _rows(SNAPSHOTS_KEY)
        rows.append({**base, "start_value": float(start_value), "latest_value": float(latest_value)})
        st.session_state[SNAPSHOTS_KEY] = rows
with buttons[3]:
    if st.button(t("clear_preview"), key="status_preview_clear"):
        st.session_state[RECORDS_KEY] = []
        st.session_state[MARKERS_KEY] = []
        st.session_state[SNAPSHOTS_KEY] = []
        st.session_state[REPORT_KEY] = {}

if st.button(t("run_preview"), key="status_preview_run"):
    st.session_state[REPORT_KEY] = build_status_preview_report(workspace_id, _rows(RECORDS_KEY), _rows(MARKERS_KEY), _rows(SNAPSHOTS_KEY))

st.markdown(f"### {t('records')}")
st.dataframe(pd.DataFrame(_rows(RECORDS_KEY)), use_container_width=True, hide_index=True)
st.markdown(f"### {t('markers')}")
st.dataframe(pd.DataFrame(_rows(MARKERS_KEY)), use_container_width=True, hide_index=True)
st.markdown(f"### {t('snapshots')}")
st.dataframe(pd.DataFrame(_rows(SNAPSHOTS_KEY)), use_container_width=True, hide_index=True)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

validation = validate_status_preview_report(report)
status_key = "ready" if report.get("status") == "READY" else "missing" if report.get("status") == "MISSING" else "review" if report.get("status") == "REVIEW" else "empty"
st.write({t(status_key): True, t("locked_logic"): bool(report.get("locked_logic"))})

metrics = st.columns(6)
metrics[0].metric("status", safe_text(report.get("status")))
metrics[1].metric("record_count", report.get("record_count", 0))
metrics[2].metric("unique_records", report.get("unique_records", 0))
metrics[3].metric("ready_count", report.get("ready_count", 0))
metrics[4].metric("review_count", report.get("review_count", 0))
metrics[5].metric("report_hash", safe_text(report.get("report_hash"))[:18])

st.markdown(f"### {t('report_summary')}")
st.json({"schema_version": report.get("schema_version"), "workspace_id": report.get("workspace_id"), "report_id": report.get("report_id"), "report_hash": report.get("report_hash"), "status": report.get("status"), "overall_passed": report.get("overall_passed"), "record_count": report.get("record_count"), "unique_records": report.get("unique_records"), "duplicate_record_count": report.get("duplicate_record_count"), "marker_count": report.get("marker_count"), "snapshot_count": report.get("snapshot_count"), "ready_count": report.get("ready_count"), "review_count": report.get("review_count"), "locked_logic": report.get("locked_logic"), "warning_count": len(report.get("warnings") or []), "error_count": len(report.get("errors") or [])})
st.markdown(f"### {t('status_rows')}")
st.dataframe(pd.DataFrame(report.get("status_rows") or []), use_container_width=True, hide_index=True)

with st.expander(t("validation"), expanded=False):
    st.json(validation)

st.download_button(t("download_report"), export_status_preview_report_json(report, public_safe=True).encode("utf-8"), file_name=_filename(report), mime="application/json", key=f"status_preview_report_json_{safe_text(report.get('report_hash'))}")

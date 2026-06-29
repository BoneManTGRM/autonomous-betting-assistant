from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.roi_clv_calibration_service import (
    build_roi_clv_calibration_report,
    export_roi_clv_calibration_report_json,
    validate_roi_clv_calibration_report,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="ROI/CLV Calibration Audit", layout="wide")
LANG = render_app_sidebar("roi_clv_calibration_audit", language_key="roi_clv_calibration_language")

ROI_CLV_PREVIEW_KEY = "roi_clv_calibration_preview"
ROI_CLV_ROWS_KEY = "roi_clv_calibration_rows"

TEXT = {
    "en": {
        "title": "ROI/CLV Calibration Audit",
        "caption": "Read-only audit for ROI math, CLV sample quality, push/cancel handling, and event-vs-row exposure.",
        "workspace_id": "Workspace ID",
        "event": "Event",
        "result": "Result",
        "stake": "Stake",
        "decimal_odds": "Decimal odds",
        "closing_decimal_odds": "Closing decimal odds",
        "add_row": "Add calibration row",
        "clear_rows": "Clear preview rows",
        "run_audit": "Run ROI/CLV audit",
        "row_ready": "Calibration row added in memory. No files were written.",
        "rows_cleared": "Preview rows cleared in memory.",
        "report_ready": "ROI/CLV calibration report generated in memory. No files were written.",
        "calibration_ok": "CALIBRATION OK",
        "calibration_warning": "CALIBRATION WARNING",
        "calibration_failed": "CALIBRATION FAILED",
        "insufficient_data": "INSUFFICIENT DATA",
        "roi_valid": "ROI VALID",
        "roi_warning": "ROI WARNING",
        "clv_valid": "CLV VALID",
        "clv_warning": "CLV WARNING",
        "event_rows": "Calibration rows",
        "report_summary": "Report summary",
        "validation": "Report validation",
        "download_report": "Download ROI/CLV calibration JSON",
        "no_report": "Run a ROI/CLV calibration audit to view report details.",
    },
    "es": {
        "title": "Auditoría de Calibración ROI/CLV",
        "caption": "Auditoría solo lectura para matemáticas ROI, calidad CLV, push/cancel y exposición evento-vs-fila.",
        "workspace_id": "ID de workspace",
        "event": "Evento",
        "result": "Resultado",
        "stake": "Stake",
        "decimal_odds": "Decimal odds",
        "closing_decimal_odds": "Closing decimal odds",
        "add_row": "Agregar fila de calibración",
        "clear_rows": "Limpiar filas de vista previa",
        "run_audit": "Ejecutar auditoría ROI/CLV",
        "row_ready": "Fila de calibración agregada en memoria. No se escribieron archivos.",
        "rows_cleared": "Filas de vista previa limpiadas en memoria.",
        "report_ready": "Reporte de calibración ROI/CLV generado en memoria. No se escribieron archivos.",
        "calibration_ok": "CALIBRATION OK",
        "calibration_warning": "CALIBRATION WARNING",
        "calibration_failed": "CALIBRATION FAILED",
        "insufficient_data": "INSUFFICIENT DATA",
        "roi_valid": "ROI VALID",
        "roi_warning": "ROI WARNING",
        "clv_valid": "CLV VALID",
        "clv_warning": "CLV WARNING",
        "event_rows": "Filas de calibración",
        "report_summary": "Resumen del reporte",
        "validation": "Validación del reporte",
        "download_report": "Descargar JSON de calibración ROI/CLV",
        "no_report": "Ejecuta una auditoría de calibración ROI/CLV para ver detalles del reporte.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _hash_fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _report_filename(report: dict) -> str:
    return f"aba_roi_clv_calibration_{safe_text(report.get('workspace_id'))}_{_hash_fragment(report.get('report_hash'))}.json"


def _row_events() -> list[dict]:
    return list(st.session_state.get(ROI_CLV_ROWS_KEY) or [])


st.title(t("title"))
st.caption(t("caption"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="roi_clv_workspace_id"))

cols = st.columns(5)
event = cols[0].text_input(t("event"), value="", key="roi_clv_event")
result = cols[1].selectbox(t("result"), ("win", "loss", "push", "cancel", "pending"), index=0, key="roi_clv_result")
stake = cols[2].number_input(t("stake"), min_value=0.0, value=1.0, step=0.5, key="roi_clv_stake")
decimal_odds = cols[3].number_input(t("decimal_odds"), min_value=0.0, value=2.0, step=0.01, key="roi_clv_decimal_odds")
closing_decimal_odds = cols[4].number_input(t("closing_decimal_odds"), min_value=0.0, value=2.0, step=0.01, key="roi_clv_closing_decimal_odds")

left, middle, right = st.columns(3)
with left:
    if st.button(t("add_row"), key="roi_clv_add_row"):
        rows = _row_events()
        rows.append({
            "workspace_id": workspace_id,
            "event": event or f"manual_event_{len(rows) + 1}",
            "result": result,
            "stake": float(stake),
            "decimal_odds": float(decimal_odds),
            "closing_decimal_odds": float(closing_decimal_odds),
        })
        st.session_state[ROI_CLV_ROWS_KEY] = rows
        st.info(t("row_ready"))
with middle:
    if st.button(t("clear_rows"), key="roi_clv_clear_rows"):
        st.session_state[ROI_CLV_ROWS_KEY] = []
        st.session_state[ROI_CLV_PREVIEW_KEY] = {}
        st.info(t("rows_cleared"))
with right:
    if st.button(t("run_audit"), key="roi_clv_run_audit"):
        report = build_roi_clv_calibration_report(workspace_id, _row_events())
        st.session_state[ROI_CLV_PREVIEW_KEY] = report
        st.info(t("report_ready"))

st.markdown(f"### {t('event_rows')}")
st.dataframe(pd.DataFrame(_row_events()), use_container_width=True, hide_index=True)

report = st.session_state.get(ROI_CLV_PREVIEW_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

validation = validate_roi_clv_calibration_report(report)
status_key = {
    "CALIBRATION OK": "calibration_ok",
    "CALIBRATION WARNING": "calibration_warning",
    "CALIBRATION FAILED": "calibration_failed",
    "INSUFFICIENT DATA": "insufficient_data",
}.get(report.get("status"), "calibration_failed")
roi_status = "roi_valid" if report.get("overall_passed") else "roi_warning"
clv_status = "clv_valid" if int(report.get("clv_sample_count") or 0) >= 10 else "clv_warning"
st.write({t(status_key): True, t(roi_status): True, t(clv_status): True})

metrics = st.columns(6)
metrics[0].metric("ROI", report.get("ROI", 0.0))
metrics[1].metric("win_rate_ex_push_cancel", report.get("win_rate_ex_push_cancel", 0.0))
metrics[2].metric("unique_events", report.get("unique_events", 0))
metrics[3].metric("row_count", report.get("row_count", 0))
metrics[4].metric("average_CLV_percent", report.get("average_CLV_percent", 0.0))
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
    "playable_count": report.get("playable_count"),
    "wins": report.get("wins"),
    "losses": report.get("losses"),
    "push_cancel_count": report.get("push_cancel_count"),
    "pending_unknown_count": report.get("pending_unknown_count"),
    "profit_units": report.get("profit_units"),
    "ROI": report.get("ROI"),
    "win_rate_ex_push_cancel": report.get("win_rate_ex_push_cancel"),
    "clv_sample_count": report.get("clv_sample_count"),
    "average_CLV_percent": report.get("average_CLV_percent"),
    "warning_count": len(report.get("warnings") or []),
    "error_count": len(report.get("errors") or []),
})

with st.expander(t("validation"), expanded=False):
    st.json(validation)

st.download_button(
    t("download_report"),
    export_roi_clv_calibration_report_json(report, public_safe=True).encode("utf-8"),
    file_name=_report_filename(report),
    mime="application/json",
    key=f"roi_clv_calibration_report_json_{safe_text(report.get('report_hash'))}",
)

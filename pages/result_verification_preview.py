from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.result_verification_preview_service import (
    build_verification_preview_report,
    export_verification_preview_report_json,
    validate_verification_preview_report,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Result Verification Preview", layout="wide")
LANG = render_app_sidebar("result_verification_preview", language_key="result_verification_preview_language")

PROOF_ROWS_KEY = "result_verification_preview_proof_rows"
SCORE_ROWS_KEY = "result_verification_preview_score_rows"
CLV_ROWS_KEY = "result_verification_preview_clv_rows"
REPORT_KEY = "result_verification_preview_report"

TEXT = {
    "en": {
        "title": "Result Verification Preview",
        "caption": "Read-only preview for final score sources, CLV payloads, grading safeguards, and manual-review flags.",
        "workspace_id": "Workspace ID",
        "event": "Event",
        "sport": "Sport",
        "market_type": "Market type",
        "pick": "Pick",
        "source": "Source",
        "home_score": "Home score",
        "away_score": "Away score",
        "confidence": "Result confidence",
        "locked_odds": "Locked decimal odds",
        "closing_odds": "Closing decimal odds",
        "add_proof_row": "Add proof row",
        "add_score_payload": "Add score payload",
        "add_clv_payload": "Add CLV payload",
        "clear_preview": "Clear preview",
        "run_preview": "Run verification preview",
        "row_ready": "Proof row added in memory. No files were written.",
        "score_ready": "Score payload added in memory. No files were written.",
        "clv_ready": "CLV payload added in memory. No files were written.",
        "cleared": "Preview cleared in memory.",
        "report_ready": "Verification preview report generated in memory. No files were written.",
        "verification_ready": "VERIFICATION READY",
        "manual_review_required": "MANUAL REVIEW REQUIRED",
        "no_rows": "NO ROWS",
        "frozen_logic": "FROZEN PICK LOGIC",
        "event_rows": "Proof rows",
        "score_rows": "Score payloads",
        "clv_rows": "CLV payloads",
        "verification_rows": "Verification rows",
        "report_summary": "Report summary",
        "validation": "Report validation",
        "download_report": "Download verification preview JSON",
        "no_report": "Run verification preview to view report details.",
    },
    "es": {
        "title": "Vista Previa de Verificación de Resultados",
        "caption": "Vista solo lectura para fuentes de score final, payloads CLV, safeguards de grading y banderas de revisión manual.",
        "workspace_id": "ID de workspace",
        "event": "Evento",
        "sport": "Sport",
        "market_type": "Tipo de mercado",
        "pick": "Pick",
        "source": "Fuente",
        "home_score": "Score local",
        "away_score": "Score visitante",
        "confidence": "Confianza del resultado",
        "locked_odds": "Locked decimal odds",
        "closing_odds": "Closing decimal odds",
        "add_proof_row": "Agregar fila de prueba",
        "add_score_payload": "Agregar payload de score",
        "add_clv_payload": "Agregar payload CLV",
        "clear_preview": "Limpiar vista previa",
        "run_preview": "Ejecutar vista de verificación",
        "row_ready": "Fila de prueba agregada en memoria. No se escribieron archivos.",
        "score_ready": "Payload de score agregado en memoria. No se escribieron archivos.",
        "clv_ready": "Payload CLV agregado en memoria. No se escribieron archivos.",
        "cleared": "Vista previa limpiada en memoria.",
        "report_ready": "Reporte de verificación generado en memoria. No se escribieron archivos.",
        "verification_ready": "VERIFICATION READY",
        "manual_review_required": "MANUAL REVIEW REQUIRED",
        "no_rows": "NO ROWS",
        "frozen_logic": "FROZEN PICK LOGIC",
        "event_rows": "Filas de prueba",
        "score_rows": "Payloads de score",
        "clv_rows": "Payloads CLV",
        "verification_rows": "Filas de verificación",
        "report_summary": "Resumen del reporte",
        "validation": "Validación del reporte",
        "download_report": "Descargar JSON de verificación",
        "no_report": "Ejecuta la vista de verificación para ver detalles del reporte.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _hash_fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _report_filename(report: dict) -> str:
    return f"aba_result_verification_{safe_text(report.get('workspace_id'))}_{_hash_fragment(report.get('report_hash'))}.json"


def _rows(key: str) -> list[dict]:
    return list(st.session_state.get(key) or [])


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="verification_workspace_id"))

cols = st.columns(5)
sport = cols[0].text_input(t("sport"), value="tennis", key="verification_sport")
event = cols[1].text_input(t("event"), value="", key="verification_event")
market_type = cols[2].selectbox(t("market_type"), ("moneyline", "spread", "total", "player_prop"), index=0, key="verification_market_type")
pick = cols[3].text_input(t("pick"), value="", key="verification_pick")
source = cols[4].text_input(t("source"), value="manual_preview", key="verification_source")

cols2 = st.columns(5)
home_score = cols2[0].number_input(t("home_score"), min_value=0.0, value=0.0, step=1.0, key="verification_home_score")
away_score = cols2[1].number_input(t("away_score"), min_value=0.0, value=0.0, step=1.0, key="verification_away_score")
confidence = cols2[2].number_input(t("confidence"), min_value=0.0, max_value=1.0, value=1.0, step=0.05, key="verification_confidence")
locked_odds = cols2[3].number_input(t("locked_odds"), min_value=0.0, value=2.0, step=0.01, key="verification_locked_odds")
closing_odds = cols2[4].number_input(t("closing_odds"), min_value=0.0, value=2.0, step=0.01, key="verification_closing_odds")

buttons = st.columns(5)
base_payload = {"workspace_id": workspace_id, "sport": sport, "event": event or "manual_event", "market_type": market_type, "pick": pick or "manual_pick", "event_start_utc": "manual_preview", "source": source or "manual_preview"}
with buttons[0]:
    if st.button(t("add_proof_row"), key="verification_add_proof_row"):
        rows = _rows(PROOF_ROWS_KEY)
        rows.append({**base_payload, "proof_id": f"preview_{len(rows) + 1}", "decimal_odds": float(locked_odds)})
        st.session_state[PROOF_ROWS_KEY] = rows
        st.info(t("row_ready"))
with buttons[1]:
    if st.button(t("add_score_payload"), key="verification_add_score_payload"):
        scores = _rows(SCORE_ROWS_KEY)
        scores.append({**base_payload, "home_score": float(home_score), "away_score": float(away_score), "result_confidence": float(confidence)})
        st.session_state[SCORE_ROWS_KEY] = scores
        st.info(t("score_ready"))
with buttons[2]:
    if st.button(t("add_clv_payload"), key="verification_add_clv_payload"):
        clv_rows = _rows(CLV_ROWS_KEY)
        clv_rows.append({**base_payload, "locked_decimal_odds": float(locked_odds), "closing_decimal_odds": float(closing_odds)})
        st.session_state[CLV_ROWS_KEY] = clv_rows
        st.info(t("clv_ready"))
with buttons[3]:
    if st.button(t("clear_preview"), key="verification_clear_preview"):
        st.session_state[PROOF_ROWS_KEY] = []
        st.session_state[SCORE_ROWS_KEY] = []
        st.session_state[CLV_ROWS_KEY] = []
        st.session_state[REPORT_KEY] = {}
        st.info(t("cleared"))
with buttons[4]:
    if st.button(t("run_preview"), key="verification_run_preview"):
        report = build_verification_preview_report(workspace_id, _rows(PROOF_ROWS_KEY), _rows(SCORE_ROWS_KEY), _rows(CLV_ROWS_KEY))
        st.session_state[REPORT_KEY] = report
        st.info(t("report_ready"))

st.markdown(f"### {t('event_rows')}")
st.dataframe(pd.DataFrame(_rows(PROOF_ROWS_KEY)), use_container_width=True, hide_index=True)
st.markdown(f"### {t('score_rows')}")
st.dataframe(pd.DataFrame(_rows(SCORE_ROWS_KEY)), use_container_width=True, hide_index=True)
st.markdown(f"### {t('clv_rows')}")
st.dataframe(pd.DataFrame(_rows(CLV_ROWS_KEY)), use_container_width=True, hide_index=True)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

validation = validate_verification_preview_report(report)
status_key = "verification_ready" if report.get("status") == "VERIFICATION READY" else "manual_review_required" if report.get("status") == "MANUAL REVIEW REQUIRED" else "no_rows"
st.write({t(status_key): True, t("frozen_logic"): bool(report.get("frozen_pick_logic"))})

metrics = st.columns(6)
metrics[0].metric("status", safe_text(report.get("status")))
metrics[1].metric("row_count", report.get("row_count", 0))
metrics[2].metric("unique_events", report.get("unique_events", 0))
metrics[3].metric("ready_count", report.get("ready_count", 0))
metrics[4].metric("manual_review_count", report.get("manual_review_count", 0))
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
    "score_payload_count": report.get("score_payload_count"),
    "clv_payload_count": report.get("clv_payload_count"),
    "ready_count": report.get("ready_count"),
    "manual_review_count": report.get("manual_review_count"),
    "frozen_pick_logic": report.get("frozen_pick_logic"),
    "warning_count": len(report.get("warnings") or []),
    "error_count": len(report.get("errors") or []),
})
st.markdown(f"### {t('verification_rows')}")
st.dataframe(pd.DataFrame(report.get("verification_rows") or []), use_container_width=True, hide_index=True)

with st.expander(t("validation"), expanded=False):
    st.json(validation)

st.download_button(
    t("download_report"),
    export_verification_preview_report_json(report, public_safe=True).encode("utf-8"),
    file_name=_report_filename(report),
    mime="application/json",
    key=f"result_verification_report_json_{safe_text(report.get('report_hash'))}",
)

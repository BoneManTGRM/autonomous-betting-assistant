from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.accuracy_calibration_repair_feedback import (
    build_accuracy_calibration_feedback_report_from_text,
    export_accuracy_calibration_json,
    export_calibrated_preview_csv,
    export_evaluation_preview_csv,
    export_repair_feedback_csv,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Accuracy Calibration Feedback", layout="wide")
LANG = render_app_sidebar("accuracy_calibration_repair_feedback", language_key="accuracy_calibration_feedback_language")

REPORT_KEY = "accuracy_calibration_feedback_report"

TEXT = {
    "en": {
        "title": "Accuracy Calibration + Repair Feedback",
        "caption": "Shadow-test probability calibration, decision downgrades, and repair feedback before any live change.",
        "workspace_id": "Workspace ID",
        "current_csv": "Current candidate rows CSV",
        "history_csv": "Historical graded rows CSV",
        "min_segment": "Min segment rows",
        "shrinkage": "Shrinkage strength",
        "ev_buffer": "EV buffer",
        "safety_margin": "Safety margin",
        "run": "Run accuracy calibration",
        "summary": "Calibration summary",
        "model": "Calibration model",
        "preview": "Current calibrated preview",
        "evaluation": "Shadow evaluation rows",
        "feedback": "Repair feedback",
        "safety": "Safety gates",
        "download_json": "Download calibration JSON",
        "download_preview": "Download calibrated preview CSV",
        "download_evaluation": "Download evaluation preview CSV",
        "download_feedback": "Download repair feedback CSV",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run accuracy calibration to view outputs.",
    },
    "es": {
        "title": "Accuracy Calibration + Repair Feedback",
        "caption": "Shadow-test de calibración de probabilidad, downgrades de decisión y feedback de repairs antes de cambios live.",
        "workspace_id": "ID de workspace",
        "current_csv": "CSV de filas candidatas actuales",
        "history_csv": "CSV de filas históricas calificadas",
        "min_segment": "Mínimo de filas por segmento",
        "shrinkage": "Fuerza de shrinkage",
        "ev_buffer": "Buffer EV",
        "safety_margin": "Margen de seguridad",
        "run": "Ejecutar calibración de accuracy",
        "summary": "Resumen de calibración",
        "model": "Modelo de calibración",
        "preview": "Preview calibrado actual",
        "evaluation": "Filas de evaluación shadow",
        "feedback": "Feedback de repairs",
        "safety": "Safety gates",
        "download_json": "Descargar JSON de calibración",
        "download_preview": "Descargar CSV preview calibrado",
        "download_evaluation": "Descargar CSV evaluación",
        "download_feedback": "Descargar CSV repair feedback",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta calibración para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "calibration"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="accuracy_calibration_workspace_id"))

cols = st.columns(4)
min_segment = cols[0].number_input(t("min_segment"), min_value=2, max_value=500, value=8, step=1, key="accuracy_calibration_min_segment")
shrinkage = cols[1].number_input(t("shrinkage"), min_value=0.0, max_value=200.0, value=20.0, step=1.0, key="accuracy_calibration_shrinkage")
ev_buffer = cols[2].number_input(t("ev_buffer"), min_value=-0.20, max_value=0.50, value=0.00, step=0.01, key="accuracy_calibration_ev_buffer")
safety_margin = cols[3].number_input(t("safety_margin"), min_value=0.00, max_value=1.00, value=0.02, step=0.01, key="accuracy_calibration_safety_margin")

current_csv = st.text_area(t("current_csv"), value="", key="accuracy_calibration_current_csv", height=180)
history_csv = st.text_area(t("history_csv"), value="", key="accuracy_calibration_history_csv", height=220)

if st.button(t("run"), key="accuracy_calibration_run"):
    st.session_state[REPORT_KEY] = build_accuracy_calibration_feedback_report_from_text(
        workspace_id,
        current_csv,
        history_csv,
        min_segment_rows=int(min_segment),
        shrinkage=float(shrinkage),
        ev_buffer=float(ev_buffer),
        safety_margin=float(safety_margin),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("decision", report.get("decision", ""))
metrics[1].metric("current", report.get("current_row_count", 0))
metrics[2].metric("history", report.get("history_row_count", 0))
metrics[3].metric("train", report.get("training_rows", 0))
metrics[4].metric("eval", report.get("evaluation_rows", 0))
metrics[5].metric("brier gain", report.get("brier_improvement"))
metrics[6].metric("feedback", report.get("repair_feedback_count", 0))
metrics[7].metric("hash", _fragment(report.get("calibration_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "calibration_id": report.get("calibration_id"),
    "calibration_hash": report.get("calibration_hash"),
    "mode": report.get("mode"),
    "decision": report.get("decision"),
    "decision_reason": report.get("decision_reason"),
    "current_row_count": report.get("current_row_count"),
    "history_row_count": report.get("history_row_count"),
    "training_rows": report.get("training_rows"),
    "evaluation_rows": report.get("evaluation_rows"),
    "baseline_brier_score": report.get("baseline_brier_score"),
    "calibrated_brier_score": report.get("calibrated_brier_score"),
    "brier_improvement": report.get("brier_improvement"),
    "baseline_log_loss": report.get("baseline_log_loss"),
    "calibrated_log_loss": report.get("calibrated_log_loss"),
    "log_loss_improvement": report.get("log_loss_improvement"),
    "calibration_error_improvement": report.get("calibration_error_improvement"),
    "playable_count": report.get("playable_count"),
    "blocked_count": report.get("blocked_count"),
    "repair_feedback_count": report.get("repair_feedback_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('model')}")
st.json({key: value for key, value in (report.get("calibration_model") or {}).items() if key != "segment_corrections"})

st.markdown(f"### {t('preview')}")
st.dataframe(pd.DataFrame(report.get("calibrated_preview_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('evaluation')}")
st.dataframe(pd.DataFrame(report.get("evaluation_preview_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('feedback')}")
st.dataframe(pd.DataFrame(report.get("repair_feedback") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('calibration_hash'))}"
st.download_button(t("download_json"), export_accuracy_calibration_json(report).encode("utf-8"), file_name=f"aba_accuracy_calibration_{suffix}.json", mime="application/json", key=f"accuracy_calibration_json_{safe_text(report.get('calibration_hash'))}")
st.download_button(t("download_preview"), export_calibrated_preview_csv(report).encode("utf-8"), file_name=f"aba_accuracy_calibrated_preview_{suffix}.csv", mime="text/csv", key=f"accuracy_calibration_preview_{safe_text(report.get('calibration_hash'))}")
st.download_button(t("download_evaluation"), export_evaluation_preview_csv(report).encode("utf-8"), file_name=f"aba_accuracy_evaluation_preview_{suffix}.csv", mime="text/csv", key=f"accuracy_calibration_evaluation_{safe_text(report.get('calibration_hash'))}")
st.download_button(t("download_feedback"), export_repair_feedback_csv(report).encode("utf-8"), file_name=f"aba_accuracy_repair_feedback_{suffix}.csv", mime="text/csv", key=f"accuracy_calibration_feedback_{safe_text(report.get('calibration_hash'))}")

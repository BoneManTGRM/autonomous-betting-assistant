from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.accuracy_decision_integration_preview import (
    build_accuracy_decision_integration_report_from_text,
    export_accuracy_decision_json,
    export_decision_preview_csv,
    export_decision_repair_feedback_csv,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Accuracy Decision Preview", layout="wide")
LANG = render_app_sidebar("accuracy_decision_integration_preview", language_key="accuracy_decision_preview_language")

REPORT_KEY = "accuracy_decision_integration_preview_report"

TEXT = {
    "en": {
        "title": "Accuracy Decision Integration Preview",
        "caption": "Use calibrated probabilities, upgraded odds math, and repair feedback to preview final pick actions before any live change.",
        "workspace_id": "Workspace ID",
        "current_csv": "Current candidate rows CSV",
        "history_csv": "Historical graded rows CSV",
        "min_segment": "Min segment rows",
        "shrinkage": "Shrinkage strength",
        "ev_buffer": "EV buffer",
        "safety_margin": "Safety margin",
        "max_age": "Max line age minutes",
        "kelly_fraction": "Kelly fraction",
        "max_stake": "Max stake fraction",
        "run": "Run decision preview",
        "summary": "Decision preview summary",
        "rows": "Decision preview rows",
        "calibration": "Calibration summary",
        "upgrade": "Odds upgrade summary",
        "feedback": "Repair feedback",
        "safety": "Safety gates",
        "download_json": "Download decision JSON",
        "download_rows": "Download decision rows CSV",
        "download_feedback": "Download repair feedback CSV",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run decision preview to view outputs.",
    },
    "es": {
        "title": "Accuracy Decision Integration Preview",
        "caption": "Usa probabilidades calibradas, odds math mejorado y repair feedback para preview de acciones finales antes de cambios live.",
        "workspace_id": "ID de workspace",
        "current_csv": "CSV de filas candidatas actuales",
        "history_csv": "CSV de filas históricas calificadas",
        "min_segment": "Mínimo de filas por segmento",
        "shrinkage": "Fuerza de shrinkage",
        "ev_buffer": "Buffer EV",
        "safety_margin": "Margen de seguridad",
        "max_age": "Edad máxima de línea en minutos",
        "kelly_fraction": "Fracción Kelly",
        "max_stake": "Fracción máxima de stake",
        "run": "Ejecutar decision preview",
        "summary": "Resumen decision preview",
        "rows": "Filas decision preview",
        "calibration": "Resumen calibración",
        "upgrade": "Resumen odds upgrade",
        "feedback": "Repair feedback",
        "safety": "Safety gates",
        "download_json": "Descargar JSON de decisión",
        "download_rows": "Descargar CSV decision rows",
        "download_feedback": "Descargar CSV repair feedback",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta decision preview para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "decision"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="accuracy_decision_workspace_id"))

cols = st.columns(6)
min_segment = cols[0].number_input(t("min_segment"), min_value=2, max_value=500, value=8, step=1, key="accuracy_decision_min_segment")
shrinkage = cols[1].number_input(t("shrinkage"), min_value=0.0, max_value=200.0, value=20.0, step=1.0, key="accuracy_decision_shrinkage")
ev_buffer = cols[2].number_input(t("ev_buffer"), min_value=-0.20, max_value=0.50, value=0.00, step=0.01, key="accuracy_decision_ev_buffer")
safety_margin = cols[3].number_input(t("safety_margin"), min_value=0.00, max_value=1.00, value=0.02, step=0.01, key="accuracy_decision_safety_margin")
max_age = cols[4].number_input(t("max_age"), min_value=1, max_value=1440, value=180, step=15, key="accuracy_decision_max_age")
kelly_fraction = cols[5].number_input(t("kelly_fraction"), min_value=0.0, max_value=1.0, value=0.25, step=0.05, key="accuracy_decision_kelly_fraction")
max_stake = st.number_input(t("max_stake"), min_value=0.0, max_value=0.25, value=0.03, step=0.01, key="accuracy_decision_max_stake")

current_csv = st.text_area(t("current_csv"), value="", key="accuracy_decision_current_csv", height=180)
history_csv = st.text_area(t("history_csv"), value="", key="accuracy_decision_history_csv", height=220)

if st.button(t("run"), key="accuracy_decision_run"):
    st.session_state[REPORT_KEY] = build_accuracy_decision_integration_report_from_text(
        workspace_id,
        current_csv,
        history_csv,
        min_segment_rows=int(min_segment),
        shrinkage=float(shrinkage),
        ev_buffer=float(ev_buffer),
        safety_margin=float(safety_margin),
        max_age_minutes=int(max_age),
        kelly_fraction=float(kelly_fraction),
        max_stake_fraction=float(max_stake),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("rows", report.get("decision_row_count", 0))
metrics[1].metric("playable", report.get("playable_count", 0))
metrics[2].metric("watch", report.get("watch_count", 0))
metrics[3].metric("wait", report.get("wait_count", 0))
metrics[4].metric("no bet", report.get("no_bet_count", 0))
metrics[5].metric("brier gain", report.get("brier_improvement"))
metrics[6].metric("feedback", report.get("repair_feedback_count", 0))
metrics[7].metric("hash", _fragment(report.get("decision_preview_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "decision_preview_id": report.get("decision_preview_id"),
    "decision_preview_hash": report.get("decision_preview_hash"),
    "mode": report.get("mode"),
    "current_row_count": report.get("current_row_count"),
    "history_row_count": report.get("history_row_count"),
    "playable_count": report.get("playable_count"),
    "watch_count": report.get("watch_count"),
    "wait_count": report.get("wait_count"),
    "no_bet_count": report.get("no_bet_count"),
    "calibration_decision": report.get("calibration_decision"),
    "calibration_decision_reason": report.get("calibration_decision_reason"),
    "brier_improvement": report.get("brier_improvement"),
    "log_loss_improvement": report.get("log_loss_improvement"),
    "repair_feedback_count": report.get("repair_feedback_count"),
    "upgrade_repair_candidate_count": report.get("upgrade_repair_candidate_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('rows')}")
st.dataframe(pd.DataFrame(report.get("decision_preview_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('calibration')}")
st.json(report.get("calibration_summary") or {})

st.markdown(f"### {t('upgrade')}")
st.json(report.get("upgrade_summary") or {})

st.markdown(f"### {t('feedback')}")
st.dataframe(pd.DataFrame(report.get("repair_feedback") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('decision_preview_hash'))}"
st.download_button(t("download_json"), export_accuracy_decision_json(report).encode("utf-8"), file_name=f"aba_accuracy_decision_{suffix}.json", mime="application/json", key=f"accuracy_decision_json_{safe_text(report.get('decision_preview_hash'))}")
st.download_button(t("download_rows"), export_decision_preview_csv(report).encode("utf-8"), file_name=f"aba_accuracy_decision_rows_{suffix}.csv", mime="text/csv", key=f"accuracy_decision_rows_{safe_text(report.get('decision_preview_hash'))}")
st.download_button(t("download_feedback"), export_decision_repair_feedback_csv(report).encode("utf-8"), file_name=f"aba_accuracy_decision_feedback_{suffix}.csv", mime="text/csv", key=f"accuracy_decision_feedback_{safe_text(report.get('decision_preview_hash'))}")

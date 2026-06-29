from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.local_review_checklist import (
    build_local_review_checklist_from_text,
    export_local_review_checklist_csv,
    export_local_review_json,
    export_local_review_manifest_json,
    export_local_review_next_actions_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Local Review Checklist", layout="wide")
LANG = render_app_sidebar("local_review_checklist", language_key="local_review_checklist_language")

REPORT_KEY = "local_review_checklist_report"

TEXT = {
    "en": {
        "title": "Local Review Checklist",
        "caption": "Verify source rows, decision preview, dashboard package, safety gates, and exports before external use.",
        "workspace_id": "Workspace ID",
        "proof_csv": "Proof / source rows CSV",
        "history_csv": "Historical graded rows CSV",
        "decision_csv": "Decision preview CSV",
        "dashboard_json": "Optional dashboard package JSON",
        "decision_json": "Optional decision package JSON",
        "ack_json": "Optional review acknowledgments JSON",
        "run": "Build review checklist",
        "summary": "Checklist summary",
        "checks": "Checklist rows",
        "actions": "Next actions",
        "manifest": "Checklist manifest",
        "safety": "Safety gates",
        "download_json": "Download checklist JSON",
        "download_checks": "Download checklist CSV",
        "download_actions": "Download next actions CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Build the checklist to view outputs.",
    },
    "es": {
        "title": "Local Review Checklist",
        "caption": "Verifica filas fuente, decision preview, dashboard package, safety gates y exports antes de uso externo.",
        "workspace_id": "ID de workspace",
        "proof_csv": "CSV proof / filas fuente",
        "history_csv": "CSV histórico calificado",
        "decision_csv": "CSV decision preview",
        "dashboard_json": "JSON dashboard package opcional",
        "decision_json": "JSON decision package opcional",
        "ack_json": "JSON acknowledgments opcional",
        "run": "Crear checklist de revisión",
        "summary": "Resumen checklist",
        "checks": "Filas checklist",
        "actions": "Siguientes acciones",
        "manifest": "Manifest checklist",
        "safety": "Safety gates",
        "download_json": "Descargar JSON checklist",
        "download_checks": "Descargar CSV checklist",
        "download_actions": "Descargar CSV acciones",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Crea el checklist para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "review"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="local_review_workspace_id"))

proof_csv = st.text_area(t("proof_csv"), value="", key="local_review_proof_csv", height=180)
history_csv = st.text_area(t("history_csv"), value="", key="local_review_history_csv", height=160)
decision_csv = st.text_area(t("decision_csv"), value="", key="local_review_decision_csv", height=160)
dashboard_json = st.text_area(t("dashboard_json"), value="", key="local_review_dashboard_json", height=140)
decision_json = st.text_area(t("decision_json"), value="", key="local_review_decision_json", height=140)
ack_json = st.text_area(t("ack_json"), value="", key="local_review_ack_json", height=100)

if st.button(t("run"), key="local_review_run"):
    st.session_state[REPORT_KEY] = build_local_review_checklist_from_text(workspace_id, proof_csv, history_csv, decision_csv, dashboard_json, decision_json, ack_json)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("readiness_status", ""))
metrics[1].metric("proof", report.get("proof_row_count", 0))
metrics[2].metric("decision", report.get("decision_row_count", 0))
metrics[3].metric("pass", report.get("pass_count", 0))
metrics[4].metric("warn", report.get("warn_count", 0))
metrics[5].metric("fail", report.get("fail_count", 0))
metrics[6].metric("required fail", report.get("required_failure_count", 0))
metrics[7].metric("hash", _fragment(report.get("local_review_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "local_review_id": report.get("local_review_id"),
    "local_review_hash": report.get("local_review_hash"),
    "mode": report.get("mode"),
    "readiness_status": report.get("readiness_status"),
    "proof_row_count": report.get("proof_row_count"),
    "history_row_count": report.get("history_row_count"),
    "decision_row_count": report.get("decision_row_count"),
    "dashboard_status": report.get("dashboard_status"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "required_failure_count": report.get("required_failure_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("checklist_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('actions')}")
st.dataframe(pd.DataFrame(report.get("next_actions") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('manifest')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "local_review_id": report.get("local_review_id"),
    "local_review_hash": report.get("local_review_hash"),
    "readiness_status": report.get("readiness_status"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
})

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('local_review_hash'))}"
st.download_button(t("download_json"), export_local_review_json(report).encode("utf-8"), file_name=f"aba_local_review_{suffix}.json", mime="application/json", key=f"local_review_json_{safe_text(report.get('local_review_hash'))}")
st.download_button(t("download_checks"), export_local_review_checklist_csv(report).encode("utf-8"), file_name=f"aba_local_review_checks_{suffix}.csv", mime="text/csv", key=f"local_review_checks_{safe_text(report.get('local_review_hash'))}")
st.download_button(t("download_actions"), export_local_review_next_actions_csv(report).encode("utf-8"), file_name=f"aba_local_review_actions_{suffix}.csv", mime="text/csv", key=f"local_review_actions_{safe_text(report.get('local_review_hash'))}")
st.download_button(t("download_manifest"), export_local_review_manifest_json(report).encode("utf-8"), file_name=f"aba_local_review_manifest_{suffix}.json", mime="application/json", key=f"local_review_manifest_{safe_text(report.get('local_review_hash'))}")

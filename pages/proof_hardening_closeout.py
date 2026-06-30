from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.proof_hardening_closeout import (
    build_proof_hardening_closeout_from_text,
    export_closeout_checks_csv,
    export_closeout_json,
    export_closeout_manifest_json,
    export_evidence_summary_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Proof Hardening Closeout", layout="wide")
LANG = render_app_sidebar("proof_hardening_closeout", language_key="proof_hardening_closeout_language")

REPORT_KEY = "proof_hardening_closeout_report"

TEXT = {
    "en": {
        "title": "Proof Hardening Closeout",
        "caption": "Issue #21 closeout gate for canonical persistence, restart recovery, proof ledger reliability, and regression evidence.",
        "workspace_id": "Workspace ID",
        "canonical": "Canonical Recovery JSON",
        "restart": "Restart Regression JSON",
        "readonly": "Read-Only Proof Audit JSON",
        "wiring": "Real Page Wiring JSON",
        "dashboard": "Dashboard Refresh JSON",
        "review": "Local Review Checklist JSON",
        "ack": "Operator acknowledges issue #21 closeout evidence is sufficient",
        "run": "Run closeout gate",
        "summary": "Closeout summary",
        "evidence": "Evidence summaries",
        "checks": "Closeout checks",
        "actions": "Next actions",
        "safety": "Safety gates",
        "download_json": "Download closeout JSON",
        "download_evidence": "Download evidence summary CSV",
        "download_checks": "Download checks CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run the closeout gate to view outputs.",
    },
    "es": {
        "title": "Proof Hardening Closeout",
        "caption": "Gate de cierre issue #21 para persistencia canonical, restart recovery, proof ledger y evidencia regression.",
        "workspace_id": "ID de workspace",
        "canonical": "JSON Canonical Recovery",
        "restart": "JSON Restart Regression",
        "readonly": "JSON Read-Only Proof Audit",
        "wiring": "JSON Real Page Wiring",
        "dashboard": "JSON Dashboard Refresh",
        "review": "JSON Local Review Checklist",
        "ack": "Operador confirma que la evidencia de issue #21 es suficiente",
        "run": "Ejecutar closeout gate",
        "summary": "Resumen closeout",
        "evidence": "Resumen de evidencia",
        "checks": "Closeout checks",
        "actions": "Siguientes acciones",
        "safety": "Safety gates",
        "download_json": "Descargar JSON closeout",
        "download_evidence": "Descargar CSV evidence summary",
        "download_checks": "Descargar CSV checks",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta el closeout gate para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "closeout"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="proof_closeout_workspace_id"))
canonical_json = st.text_area(t("canonical"), value="", key="proof_closeout_canonical_json", height=120)
restart_json = st.text_area(t("restart"), value="", key="proof_closeout_restart_json", height=120)
readonly_json = st.text_area(t("readonly"), value="", key="proof_closeout_readonly_json", height=120)
wiring_json = st.text_area(t("wiring"), value="", key="proof_closeout_wiring_json", height=120)
dashboard_json = st.text_area(t("dashboard"), value="", key="proof_closeout_dashboard_json", height=120)
review_json = st.text_area(t("review"), value="", key="proof_closeout_review_json", height=120)
ack = st.checkbox(t("ack"), value=False, key="proof_closeout_operator_ack")

if st.button(t("run"), key="proof_closeout_run"):
    st.session_state[REPORT_KEY] = build_proof_hardening_closeout_from_text(workspace_id, canonical_json, restart_json, readonly_json, wiring_json, dashboard_json, review_json, ack)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("closeout_status", ""))
metrics[1].metric("recommendation", report.get("issue_21_recommendation", ""))
metrics[2].metric("pass", report.get("pass_count", 0))
metrics[3].metric("warn", report.get("warn_count", 0))
metrics[4].metric("fail", report.get("fail_count", 0))
metrics[5].metric("ack", str(bool(report.get("operator_acknowledged"))))
metrics[6].metric("evidence", len(report.get("evidence_summaries") or []))
metrics[7].metric("hash", _fragment(report.get("closeout_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "closeout_id": report.get("closeout_id"),
    "closeout_hash": report.get("closeout_hash"),
    "mode": report.get("mode"),
    "closeout_status": report.get("closeout_status"),
    "issue_21_recommendation": report.get("issue_21_recommendation"),
    "operator_acknowledged": report.get("operator_acknowledged"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('evidence')}")
st.dataframe(pd.DataFrame(report.get("evidence_summaries") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("closeout_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('actions')}")
st.write(report.get("next_actions") or [])

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('closeout_hash'))}"
st.download_button(t("download_json"), export_closeout_json(report).encode("utf-8"), file_name=f"aba_proof_hardening_closeout_{suffix}.json", mime="application/json", key=f"proof_closeout_json_{safe_text(report.get('closeout_hash'))}")
st.download_button(t("download_evidence"), export_evidence_summary_csv(report).encode("utf-8"), file_name=f"aba_proof_hardening_evidence_{suffix}.csv", mime="text/csv", key=f"proof_closeout_evidence_{safe_text(report.get('closeout_hash'))}")
st.download_button(t("download_checks"), export_closeout_checks_csv(report).encode("utf-8"), file_name=f"aba_proof_hardening_checks_{suffix}.csv", mime="text/csv", key=f"proof_closeout_checks_{safe_text(report.get('closeout_hash'))}")
st.download_button(t("download_manifest"), export_closeout_manifest_json(report).encode("utf-8"), file_name=f"aba_proof_hardening_manifest_{suffix}.json", mime="application/json", key=f"proof_closeout_manifest_{safe_text(report.get('closeout_hash'))}")

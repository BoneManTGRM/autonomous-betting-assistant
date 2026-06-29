from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.proof_ledger_readonly_audit import (
    build_proof_ledger_readonly_audit_from_text,
    export_proof_audit_checks_csv,
    export_proof_audit_duplicates_csv,
    export_proof_audit_json,
    export_proof_audit_manifest_json,
    export_proof_audit_summaries_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Proof Ledger Read-Only Audit", layout="wide")
LANG = render_app_sidebar("proof_ledger_readonly_audit", language_key="proof_ledger_audit_language")

REPORT_KEY = "proof_ledger_readonly_audit_report"

TEXT = {
    "en": {
        "title": "Proof Ledger Read-Only Audit",
        "caption": "Audit proof, learning, dashboard, decision, page, and store handoffs without changing source data.",
        "workspace_id": "Workspace ID",
        "proof_csv": "Proof / source rows CSV",
        "learning_csv": "Learning rows CSV",
        "dashboard_csv": "Dashboard rows CSV",
        "decision_csv": "Decision rows CSV",
        "page_csv": "Page inventory CSV",
        "store_csv": "Store inventory CSV",
        "dashboard_json": "Optional dashboard package JSON",
        "run": "Run read-only audit",
        "summary": "Audit summary",
        "checks": "Audit checks",
        "datasets": "Dataset summaries",
        "duplicates": "Duplicate event groups",
        "pages": "Page inventory",
        "stores": "Store inventory",
        "safety": "Safety gates",
        "download_json": "Download audit JSON",
        "download_checks": "Download checks CSV",
        "download_summaries": "Download summaries CSV",
        "download_duplicates": "Download duplicates CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run the read-only audit to view outputs.",
    },
    "es": {
        "title": "Proof Ledger Read-Only Audit",
        "caption": "Audita handoffs de proof, learning, dashboard, decision, pages y stores sin cambiar datos fuente.",
        "workspace_id": "ID de workspace",
        "proof_csv": "CSV proof / filas fuente",
        "learning_csv": "CSV learning rows",
        "dashboard_csv": "CSV dashboard rows",
        "decision_csv": "CSV decision rows",
        "page_csv": "CSV inventario de páginas",
        "store_csv": "CSV inventario de stores",
        "dashboard_json": "JSON dashboard package opcional",
        "run": "Ejecutar audit read-only",
        "summary": "Resumen audit",
        "checks": "Audit checks",
        "datasets": "Resumen datasets",
        "duplicates": "Grupos duplicados de eventos",
        "pages": "Inventario de páginas",
        "stores": "Inventario de stores",
        "safety": "Safety gates",
        "download_json": "Descargar JSON audit",
        "download_checks": "Descargar CSV checks",
        "download_summaries": "Descargar CSV summaries",
        "download_duplicates": "Descargar CSV duplicados",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta el audit read-only para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "audit"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="proof_audit_workspace_id"))

proof_csv = st.text_area(t("proof_csv"), value="", key="proof_audit_proof_csv", height=160)
learning_csv = st.text_area(t("learning_csv"), value="", key="proof_audit_learning_csv", height=140)
dashboard_csv = st.text_area(t("dashboard_csv"), value="", key="proof_audit_dashboard_csv", height=140)
decision_csv = st.text_area(t("decision_csv"), value="", key="proof_audit_decision_csv", height=140)
page_csv = st.text_area(t("page_csv"), value="", key="proof_audit_page_csv", height=120)
store_csv = st.text_area(t("store_csv"), value="", key="proof_audit_store_csv", height=120)
dashboard_json = st.text_area(t("dashboard_json"), value="", key="proof_audit_dashboard_json", height=120)

if st.button(t("run"), key="proof_audit_run"):
    st.session_state[REPORT_KEY] = build_proof_ledger_readonly_audit_from_text(workspace_id, proof_csv, learning_csv, dashboard_csv, decision_csv, page_csv, store_csv, dashboard_json)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("audit_status", ""))
metrics[1].metric("proof", report.get("proof_row_count", 0))
metrics[2].metric("learning", report.get("learning_row_count", 0))
metrics[3].metric("dashboard", report.get("dashboard_row_count", 0))
metrics[4].metric("decision", report.get("decision_row_count", 0))
metrics[5].metric("warn", report.get("warn_count", 0))
metrics[6].metric("fail", report.get("fail_count", 0))
metrics[7].metric("hash", _fragment(report.get("audit_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "audit_id": report.get("audit_id"),
    "audit_hash": report.get("audit_hash"),
    "mode": report.get("mode"),
    "audit_status": report.get("audit_status"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "proof_row_count": report.get("proof_row_count"),
    "learning_row_count": report.get("learning_row_count"),
    "dashboard_row_count": report.get("dashboard_row_count"),
    "decision_row_count": report.get("decision_row_count"),
    "page_inventory_count": report.get("page_inventory_count"),
    "store_inventory_count": report.get("store_inventory_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("audit_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('datasets')}")
st.dataframe(pd.DataFrame(report.get("dataset_summaries") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('duplicates')}")
st.dataframe(pd.DataFrame(report.get("duplicate_event_groups") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('pages')}")
st.dataframe(pd.DataFrame(report.get("page_inventory") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('stores')}")
st.dataframe(pd.DataFrame(report.get("store_inventory") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('audit_hash'))}"
st.download_button(t("download_json"), export_proof_audit_json(report).encode("utf-8"), file_name=f"aba_proof_audit_{suffix}.json", mime="application/json", key=f"proof_audit_json_{safe_text(report.get('audit_hash'))}")
st.download_button(t("download_checks"), export_proof_audit_checks_csv(report).encode("utf-8"), file_name=f"aba_proof_audit_checks_{suffix}.csv", mime="text/csv", key=f"proof_audit_checks_{safe_text(report.get('audit_hash'))}")
st.download_button(t("download_summaries"), export_proof_audit_summaries_csv(report).encode("utf-8"), file_name=f"aba_proof_audit_summaries_{suffix}.csv", mime="text/csv", key=f"proof_audit_summaries_{safe_text(report.get('audit_hash'))}")
st.download_button(t("download_duplicates"), export_proof_audit_duplicates_csv(report).encode("utf-8"), file_name=f"aba_proof_audit_duplicates_{suffix}.csv", mime="text/csv", key=f"proof_audit_duplicates_{safe_text(report.get('audit_hash'))}")
st.download_button(t("download_manifest"), export_proof_audit_manifest_json(report).encode("utf-8"), file_name=f"aba_proof_audit_manifest_{suffix}.json", mime="application/json", key=f"proof_audit_manifest_{safe_text(report.get('audit_hash'))}")

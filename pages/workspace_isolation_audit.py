from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.proof_archive_service import build_proof_archive_index
from autonomous_betting_agent.proof_package_integrity_service import build_proof_package_qa_report
from autonomous_betting_agent.proof_package_service import build_client_summary_package, build_public_proof_package
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.workspace_isolation_service import (
    build_workspace_isolation_report,
    export_workspace_isolation_report_json,
    validate_workspace_id,
    validate_workspace_isolation_report,
)

st.set_page_config(page_title="Workspace Isolation Audit", layout="wide")
LANG = render_app_sidebar("workspace_isolation_audit", language_key="workspace_isolation_language")

WORKSPACE_ISOLATION_PREVIEW_KEY = "workspace_isolation_audit_preview"
WORKSPACE_ISOLATION_PUBLIC_PACKAGE_KEY = "workspace_isolation_public_package"
WORKSPACE_ISOLATION_CLIENT_PACKAGE_KEY = "workspace_isolation_client_package"
WORKSPACE_ISOLATION_QA_KEY = "workspace_isolation_qa_report"
WORKSPACE_ISOLATION_ARCHIVE_KEY = "workspace_isolation_archive_index"

TEXT = {
    "en": {
        "title": "Workspace Isolation Audit",
        "caption": "Read-only check that workspace/client artifacts do not leak across tenant boundaries.",
        "workspace_id": "Workspace ID",
        "build_artifacts": "Build read-only artifacts",
        "run_audit": "Run workspace isolation audit",
        "artifacts_ready": "Artifacts built in memory. No files were written.",
        "audit_ready": "Workspace isolation audit complete. No files were written.",
        "workspace_valid": "workspace_id validation",
        "overall_passed": "overall_passed",
        "checked_objects": "checked_object_count",
        "failed_objects": "failed_object_count",
        "cross_leakage": "cross_workspace_leakage_count",
        "private_markers": "private_marker_count",
        "public_client_mode": "public_client_mode",
        "isolation_passed": "WORKSPACE ISOLATION PASSED",
        "isolation_failed": "WORKSPACE ISOLATION FAILED",
        "no_cross_workspace": "NO CROSS-WORKSPACE LEAKAGE",
        "cross_workspace_warning": "CROSS-WORKSPACE WARNING",
        "public_client_safe": "PUBLIC/CLIENT SAFE",
        "public_client_blocked": "PUBLIC/CLIENT BLOCKED",
        "audit_summary": "Audit summary",
        "object_results": "Object results",
        "validation": "Report validation",
        "download_report": "Download workspace isolation report JSON",
        "no_report": "Run a workspace isolation audit to view results.",
    },
    "es": {
        "title": "Auditoría de Aislamiento de Workspace",
        "caption": "Revisión solo lectura para confirmar que artefactos de workspace/cliente no se mezclan entre tenants.",
        "workspace_id": "ID de workspace",
        "build_artifacts": "Crear artefactos solo lectura",
        "run_audit": "Ejecutar auditoría de aislamiento",
        "artifacts_ready": "Artefactos creados en memoria. No se escribieron archivos.",
        "audit_ready": "Auditoría de aislamiento completa. No se escribieron archivos.",
        "workspace_valid": "validación de workspace_id",
        "overall_passed": "overall_passed",
        "checked_objects": "checked_object_count",
        "failed_objects": "failed_object_count",
        "cross_leakage": "cross_workspace_leakage_count",
        "private_markers": "private_marker_count",
        "public_client_mode": "public_client_mode",
        "isolation_passed": "WORKSPACE ISOLATION PASSED",
        "isolation_failed": "WORKSPACE ISOLATION FAILED",
        "no_cross_workspace": "NO CROSS-WORKSPACE LEAKAGE",
        "cross_workspace_warning": "CROSS-WORKSPACE WARNING",
        "public_client_safe": "PUBLIC/CLIENT SAFE",
        "public_client_blocked": "PUBLIC/CLIENT BLOCKED",
        "audit_summary": "Resumen de auditoría",
        "object_results": "Resultados por objeto",
        "validation": "Validación del reporte",
        "download_report": "Descargar JSON del reporte de aislamiento",
        "no_report": "Ejecuta una auditoría de aislamiento para ver resultados.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _hash_fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _report_filename(report: dict) -> str:
    return f"aba_workspace_isolation_{safe_text(report.get('workspace_id'))}_{_hash_fragment(report.get('report_hash'))}.json"


def _artifact_payload() -> dict:
    payload = {}
    if st.session_state.get(WORKSPACE_ISOLATION_PUBLIC_PACKAGE_KEY):
        payload["public_package"] = st.session_state[WORKSPACE_ISOLATION_PUBLIC_PACKAGE_KEY]
    if st.session_state.get(WORKSPACE_ISOLATION_CLIENT_PACKAGE_KEY):
        payload["client_package"] = st.session_state[WORKSPACE_ISOLATION_CLIENT_PACKAGE_KEY]
    if st.session_state.get(WORKSPACE_ISOLATION_QA_KEY):
        payload["qa_report"] = st.session_state[WORKSPACE_ISOLATION_QA_KEY]
    if st.session_state.get(WORKSPACE_ISOLATION_ARCHIVE_KEY):
        payload["archive_snapshots"] = st.session_state[WORKSPACE_ISOLATION_ARCHIVE_KEY].get("snapshots") or []
    return payload


st.title(t("title"))
st.caption(t("caption"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="workspace_isolation_workspace_id"))
workspace_check = validate_workspace_id(workspace_id)
st.write({t("workspace_valid"): workspace_check.get("passed"), "warnings": len(workspace_check.get("warnings") or []), "errors": len(workspace_check.get("errors") or [])})

left, right = st.columns(2)
with left:
    if st.button(t("build_artifacts"), key="workspace_isolation_build_artifacts"):
        st.session_state[WORKSPACE_ISOLATION_PUBLIC_PACKAGE_KEY] = build_public_proof_package(workspace_id)
        st.session_state[WORKSPACE_ISOLATION_CLIENT_PACKAGE_KEY] = build_client_summary_package(workspace_id)
        st.session_state[WORKSPACE_ISOLATION_QA_KEY] = build_proof_package_qa_report(workspace_id, "public")
        st.session_state[WORKSPACE_ISOLATION_ARCHIVE_KEY] = build_proof_archive_index(workspace_id)
        st.info(t("artifacts_ready"))
with right:
    if st.button(t("run_audit"), key="workspace_isolation_run_audit"):
        report = build_workspace_isolation_report(workspace_id, _artifact_payload(), public_client=True)
        st.session_state[WORKSPACE_ISOLATION_PREVIEW_KEY] = report
        st.info(t("audit_ready"))

report = st.session_state.get(WORKSPACE_ISOLATION_PREVIEW_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

validation = validate_workspace_isolation_report(report)
status = t("isolation_passed") if report.get("overall_passed") else t("isolation_failed")
leakage_status = t("no_cross_workspace") if not report.get("cross_workspace_leakage_count") else t("cross_workspace_warning")
safety_status = t("public_client_safe") if not report.get("private_marker_count") else t("public_client_blocked")
st.write({status: True, leakage_status: True, safety_status: True})

metrics = st.columns(6)
metrics[0].metric(t("overall_passed"), str(bool(report.get("overall_passed"))))
metrics[1].metric(t("checked_objects"), report.get("checked_object_count", 0))
metrics[2].metric(t("failed_objects"), report.get("failed_object_count", 0))
metrics[3].metric(t("cross_leakage"), report.get("cross_workspace_leakage_count", 0))
metrics[4].metric(t("private_markers"), report.get("private_marker_count", 0))
metrics[5].metric(t("public_client_mode"), str(bool(report.get("public_client_mode"))))

st.markdown(f"### {t('audit_summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "report_id": report.get("report_id"),
    "report_hash": report.get("report_hash"),
    "workspace_id_valid": report.get("workspace_id_valid"),
    "checked_artifact_count": report.get("checked_artifact_count"),
    "checked_object_count": report.get("checked_object_count"),
    "failed_object_count": report.get("failed_object_count"),
    "cross_workspace_leakage_count": report.get("cross_workspace_leakage_count"),
    "missing_workspace_count": report.get("missing_workspace_count"),
    "private_marker_count": report.get("private_marker_count"),
    "overall_passed": report.get("overall_passed"),
})

st.markdown(f"### {t('object_results')}")
object_rows = []
for row in report.get("object_results") or []:
    object_rows.append({
        "artifact_name": row.get("artifact_name"),
        "index": row.get("index"),
        "passed": row.get("passed"),
        "object_type": row.get("object_type"),
        "object_workspace_id": row.get("object_workspace_id"),
        "error_count": len(row.get("errors") or []),
        "blocked_terms_count": row.get("blocked_terms_count", 0),
        "blocked_paths_count": row.get("blocked_paths_count", 0),
    })
st.dataframe(pd.DataFrame(object_rows), use_container_width=True, hide_index=True)

with st.expander(t("validation"), expanded=False):
    st.json(validation)

st.download_button(
    t("download_report"),
    export_workspace_isolation_report_json(report, public_safe=True).encode("utf-8"),
    file_name=_report_filename(report),
    mime="application/json",
    key=f"workspace_isolation_report_json_{safe_text(report.get('report_hash'))}",
)

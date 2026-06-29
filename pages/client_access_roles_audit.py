from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.client_access_roles_service import (
    CLIENT_ACCESS_ROLES,
    build_client_access_audit_report,
    build_client_access_role_matrix,
    export_client_access_audit_report_json,
    get_role_access_policy,
    validate_client_access_audit_report,
    validate_role_access,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Client Access Roles Audit", layout="wide")
LANG = render_app_sidebar("client_access_roles_audit", language_key="client_access_roles_language")

CLIENT_ACCESS_AUDIT_PREVIEW_KEY = "client_access_roles_audit_preview"
CLIENT_ACCESS_MATRIX_PREVIEW_KEY = "client_access_roles_matrix_preview"

TEXT = {
    "en": {
        "title": "Client Access Roles Audit",
        "caption": "Read-only SaaS-prep role policy view for admin, operator, client, demo, and public access.",
        "role": "Role",
        "resource": "Resource",
        "action": "Action",
        "package_type": "package_type",
        "run_access_check": "Run access check",
        "run_role_audit": "Run role audit",
        "build_matrix": "Build role matrix",
        "access_allowed": "ACCESS ALLOWED",
        "access_blocked": "ACCESS BLOCKED",
        "private_internal_allowed": "PRIVATE/INTERNAL ALLOWED",
        "private_internal_blocked": "PRIVATE/INTERNAL BLOCKED",
        "operator_only": "OPERATOR ONLY",
        "client_safe": "CLIENT SAFE",
        "policy": "Role policy",
        "audit_summary": "Audit summary",
        "checks": "Checks",
        "matrix": "Role matrix",
        "validation": "Report validation",
        "download_report": "Download role audit JSON",
        "report_ready": "Role audit generated in memory. No files were written.",
        "matrix_ready": "Role matrix generated in memory. No files were written.",
        "no_report": "Run a role audit to view report details.",
    },
    "es": {
        "title": "Auditoría de Roles de Acceso de Cliente",
        "caption": "Vista solo lectura de políticas de rol para preparar SaaS: admin, operator, client, demo y public.",
        "role": "Rol",
        "resource": "Recurso",
        "action": "Acción",
        "package_type": "package_type",
        "run_access_check": "Ejecutar revisión de acceso",
        "run_role_audit": "Ejecutar auditoría de rol",
        "build_matrix": "Crear matriz de roles",
        "access_allowed": "ACCESS ALLOWED",
        "access_blocked": "ACCESS BLOCKED",
        "private_internal_allowed": "PRIVATE/INTERNAL ALLOWED",
        "private_internal_blocked": "PRIVATE/INTERNAL BLOCKED",
        "operator_only": "OPERATOR ONLY",
        "client_safe": "CLIENT SAFE",
        "policy": "Política de rol",
        "audit_summary": "Resumen de auditoría",
        "checks": "Revisiones",
        "matrix": "Matriz de roles",
        "validation": "Validación del reporte",
        "download_report": "Descargar JSON de auditoría de rol",
        "report_ready": "Auditoría de rol generada en memoria. No se escribieron archivos.",
        "matrix_ready": "Matriz de roles generada en memoria. No se escribieron archivos.",
        "no_report": "Ejecuta una auditoría de rol para ver detalles del reporte.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _hash_fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "nohash"


def _report_filename(report: dict) -> str:
    return f"aba_client_access_roles_{safe_text(report.get('role'))}_{_hash_fragment(report.get('report_hash'))}.json"


def _checks_frame(report: dict) -> pd.DataFrame:
    rows = []
    for check in report.get("checks") or []:
        rows.append({
            "role": check.get("role"),
            "resource": check.get("resource"),
            "action": check.get("action"),
            "package_type": check.get("package_type"),
            "allowed": check.get("allowed"),
            "error_count": len(check.get("errors") or []),
            "warning_count": len(check.get("warnings") or []),
        })
    return pd.DataFrame(rows)


st.title(t("title"))
st.caption(t("caption"))

role = st.selectbox(t("role"), CLIENT_ACCESS_ROLES, index=2, key="client_access_role_selector")
resource = st.selectbox(t("resource"), ("dashboard", "proof_center", "report_studio", "public_proof_share", "client_proof_viewer", "proof_archive_viewer", "workspace_isolation_audit", "proof_package", "qa_report", "archive_snapshot"), index=4, key="client_access_resource_selector")
action = st.selectbox(t("action"), ("view", "download_json", "download_markdown", "download_csv", "run_qa", "run_e2e_qa", "approve_import", "view_private_audit", "view_public_share", "view_client_viewer", "view_archive", "view_workspace_audit"), index=0, key="client_access_action_selector")
package_type = st.selectbox(t("package_type"), ("public", "client", "private", "internal_review"), index=1, key="client_access_package_type_selector")

check_result = validate_role_access(role, resource, action, package_type)
status = t("access_allowed") if check_result.get("allowed") else t("access_blocked")
private_status = t("private_internal_allowed") if get_role_access_policy(role).get("private_internal_allowed") else t("private_internal_blocked")
client_status = t("operator_only") if role in {"admin", "operator"} else t("client_safe")
st.write({status: True, private_status: True, client_status: True})

left, right = st.columns(2)
with left:
    if st.button(t("run_role_audit"), key="client_access_run_role_audit"):
        report = build_client_access_audit_report(role)
        st.session_state[CLIENT_ACCESS_AUDIT_PREVIEW_KEY] = report
        st.info(t("report_ready"))
with right:
    if st.button(t("build_matrix"), key="client_access_build_matrix"):
        matrix = build_client_access_role_matrix()
        st.session_state[CLIENT_ACCESS_MATRIX_PREVIEW_KEY] = matrix
        st.info(t("matrix_ready"))

with st.expander(t("policy"), expanded=False):
    st.json(get_role_access_policy(role))

report = st.session_state.get(CLIENT_ACCESS_AUDIT_PREVIEW_KEY, {})
if report:
    validation = validate_client_access_audit_report(report)
    st.markdown(f"### {t('audit_summary')}")
    metrics = st.columns(6)
    metrics[0].metric("overall_passed", str(bool(report.get("overall_passed"))))
    metrics[1].metric("allowed_count", report.get("allowed_count", 0))
    metrics[2].metric("denied_count", report.get("denied_count", 0))
    metrics[3].metric("private_denial_count", report.get("private_denial_count", 0))
    metrics[4].metric("unexpected_private_allow_count", report.get("unexpected_private_allow_count", 0))
    metrics[5].metric("report_hash", safe_text(report.get("report_hash"))[:18])
    st.json({
        "schema_version": report.get("schema_version"),
        "report_id": report.get("report_id"),
        "report_hash": report.get("report_hash"),
        "role": report.get("role"),
        "check_count": report.get("check_count"),
        "overall_passed": report.get("overall_passed"),
    })
    st.markdown(f"### {t('checks')}")
    st.dataframe(_checks_frame(report), use_container_width=True, hide_index=True)
    with st.expander(t("validation"), expanded=False):
        st.json(validation)
    st.download_button(
        t("download_report"),
        export_client_access_audit_report_json(report, public_safe=True).encode("utf-8"),
        file_name=_report_filename(report),
        mime="application/json",
        key=f"client_access_roles_report_json_{safe_text(report.get('report_hash'))}",
    )
else:
    st.info(t("no_report"))

matrix = st.session_state.get(CLIENT_ACCESS_MATRIX_PREVIEW_KEY, {})
if matrix:
    st.markdown(f"### {t('matrix')}")
    st.dataframe(pd.DataFrame(matrix.get("rows") or []), use_container_width=True, hide_index=True)
    st.caption(safe_text(matrix.get("matrix_hash")))

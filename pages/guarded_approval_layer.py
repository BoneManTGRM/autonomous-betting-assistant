from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.guarded_approval_layer import (
    REQUIRED_PHRASE,
    build_guarded_approval_package_from_text,
    export_approval_manifest_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Guarded Approval Layer", layout="wide")
LANG = render_app_sidebar("guarded_approval_layer", language_key="guarded_approval_language")

PACKAGE_KEY = "guarded_approval_package"

TEXT = {
    "en": {
        "title": "Guarded Approval Layer",
        "caption": "Manual approval gate for turning a reviewed preview into an approved downloadable package. It does not write files or change proof data.",
        "workspace_id": "Workspace ID",
        "base_csv": "Current locked/base CSV",
        "candidate_csv": "Candidate updated-preview CSV",
        "manifest_json": "Package or simulation manifest JSON",
        "operator_name": "Operator name",
        "approval_note": "Approval note",
        "approval_phrase": "Approval phrase",
        "required_phrase": "Required phrase",
        "run": "Build guarded approval package",
        "approved": "APPROVED PACKAGE",
        "blocked": "APPROVAL BLOCKED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "summary": "Approval summary",
        "diff_rows": "Diff rows",
        "blocked_reasons": "Blocked reasons",
        "manifest": "Download approval manifest JSON",
        "backup": "Download backup CSV",
        "approved_csv": "Download approved CSV",
        "rollback": "Download rollback CSV",
        "audit": "Download audit JSON",
        "no_package": "Build a guarded approval package to view outputs.",
    },
    "es": {
        "title": "Capa Guarded de Approval",
        "caption": "Puerta de aprobación manual para convertir un preview revisado en paquete descargable aprobado. No escribe archivos ni cambia proof data.",
        "workspace_id": "ID de workspace",
        "base_csv": "CSV actual bloqueado/base",
        "candidate_csv": "CSV preview actualizado candidato",
        "manifest_json": "JSON manifest del paquete o simulación",
        "operator_name": "Nombre del operador",
        "approval_note": "Nota de aprobación",
        "approval_phrase": "Frase de aprobación",
        "required_phrase": "Frase requerida",
        "run": "Construir paquete guarded approval",
        "approved": "APPROVED PACKAGE",
        "blocked": "APPROVAL BLOCKED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "summary": "Resumen de aprobación",
        "diff_rows": "Filas diff",
        "blocked_reasons": "Razones bloqueadas",
        "manifest": "Descargar manifest JSON approval",
        "backup": "Descargar backup CSV",
        "approved_csv": "Descargar CSV aprobado",
        "rollback": "Descargar rollback CSV",
        "audit": "Descargar audit JSON",
        "no_package": "Construye un paquete guarded approval para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "approval"


st.title(t("title"))
st.caption(t("caption"))
st.info(f"{t('required_phrase')}: {REQUIRED_PHRASE}")

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="guarded_approval_workspace_id"))
operator_name = st.text_input(t("operator_name"), value="", key="guarded_approval_operator_name")
approval_note = st.text_area(t("approval_note"), value="", key="guarded_approval_note", height=90)
approval_phrase = st.text_input(t("approval_phrase"), value="", key="guarded_approval_phrase")

base_csv = st.text_area(t("base_csv"), value="", key="guarded_approval_base_csv", height=160)
candidate_csv = st.text_area(t("candidate_csv"), value="", key="guarded_approval_candidate_csv", height=160)
manifest_json = st.text_area(t("manifest_json"), value="", key="guarded_approval_manifest_json", height=140)

if st.button(t("run"), key="guarded_approval_run"):
    st.session_state[PACKAGE_KEY] = build_guarded_approval_package_from_text(
        workspace_id,
        base_csv,
        candidate_csv,
        manifest_json,
        approval_phrase,
        operator_name,
        approval_note,
    )

package = st.session_state.get(PACKAGE_KEY, {})
if not package:
    st.info(t("no_package"))
    st.stop()

status = safe_text(package.get("status"))
status_key = "approved" if status == "APPROVED PACKAGE" else "empty" if status == "NO ROWS" else "blocked"
st.write({t(status_key): True, t("preview_only"): bool(package.get("preview_only")), t("no_files"): int(package.get("files_written") or 0) == 0, t("no_live"): int(package.get("live_changes") or 0) == 0})

metrics = st.columns(6)
metrics[0].metric("status", status)
metrics[1].metric("base", package.get("base_row_count", 0))
metrics[2].metric("candidate", package.get("candidate_row_count", 0))
metrics[3].metric("changed", package.get("changed_row_count", 0))
metrics[4].metric("blocked", package.get("blocked_reason_count", 0))
metrics[5].metric("hash", _fragment(package.get("approval_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": package.get("schema_version"),
    "workspace_id": package.get("workspace_id"),
    "approval_id": package.get("approval_id"),
    "approval_hash": package.get("approval_hash"),
    "status": package.get("status"),
    "base_row_count": package.get("base_row_count"),
    "candidate_row_count": package.get("candidate_row_count"),
    "changed_row_count": package.get("changed_row_count"),
    "blocked_reason_count": package.get("blocked_reason_count"),
    "approval_phrase_required": package.get("approval_phrase_required"),
    "approval_phrase_matched": package.get("approval_phrase_matched"),
    "preview_only": package.get("preview_only"),
    "files_written": package.get("files_written"),
    "live_changes": package.get("live_changes"),
})

st.markdown(f"### {t('diff_rows')}")
st.dataframe(pd.DataFrame(package.get("diff_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('blocked_reasons')}")
st.dataframe(pd.DataFrame([{"reason": item} for item in package.get("blocked_reasons") or []]), use_container_width=True, hide_index=True)

suffix = f"{safe_text(package.get('workspace_id'))}_{_fragment(package.get('approval_hash'))}"
st.download_button(t("manifest"), export_approval_manifest_json(package).encode("utf-8"), file_name=f"aba_guarded_approval_manifest_{suffix}.json", mime="application/json", key=f"guarded_approval_manifest_{safe_text(package.get('approval_hash'))}")
st.download_button(t("backup"), safe_text(package.get("backup_csv")).encode("utf-8"), file_name=f"aba_guarded_approval_backup_{suffix}.csv", mime="text/csv", key=f"guarded_approval_backup_{safe_text(package.get('approval_hash'))}")
st.download_button(t("approved_csv"), safe_text(package.get("approved_csv")).encode("utf-8"), file_name=f"aba_guarded_approval_approved_{suffix}.csv", mime="text/csv", key=f"guarded_approval_approved_{safe_text(package.get('approval_hash'))}")
st.download_button(t("rollback"), safe_text(package.get("rollback_csv")).encode("utf-8"), file_name=f"aba_guarded_approval_rollback_{suffix}.csv", mime="text/csv", key=f"guarded_approval_rollback_{safe_text(package.get('approval_hash'))}")
st.download_button(t("audit"), safe_text(package.get("audit_json")).encode("utf-8"), file_name=f"aba_guarded_approval_audit_{suffix}.json", mime="application/json", key=f"guarded_approval_audit_{safe_text(package.get('approval_hash'))}")

from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.offline_update_package_builder import (
    build_offline_update_package_from_text,
    export_package_manifest_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Offline Update Package Builder", layout="wide")
LANG = render_app_sidebar("offline_update_package_builder", language_key="offline_update_package_language")

PACKAGE_KEY = "offline_update_package"

TEXT = {
    "en": {
        "title": "Offline Update Package Builder",
        "caption": "Build a downloadable backup, preview, rollback, audit, diff, and verified-learning package without changing stored proof data.",
        "workspace_id": "Workspace ID",
        "locked_csv": "Locked proof CSV",
        "match_report_json": "Event match report JSON",
        "confirmation_json": "Confirmation payload JSON",
        "value_json": "Value payload JSON",
        "run": "Build offline package",
        "ready": "PACKAGE READY",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "summary": "Package summary",
        "diff_rows": "Diff rows",
        "review_rows": "Manual review rows",
        "learning_rows": "Verified learning rows",
        "manifest": "Download manifest JSON",
        "backup": "Download backup CSV",
        "updated": "Download updated preview CSV",
        "rollback": "Download rollback CSV",
        "audit": "Download audit JSON",
        "no_package": "Build an offline package to view outputs.",
    },
    "es": {
        "title": "Constructor Offline de Paquete de Actualización",
        "caption": "Construye backup, preview, rollback, audit, diff y learning verificado sin cambiar datos proof guardados.",
        "workspace_id": "ID de workspace",
        "locked_csv": "CSV proof bloqueado",
        "match_report_json": "JSON del reporte de match de evento",
        "confirmation_json": "JSON de payload de confirmación",
        "value_json": "JSON de payload de valor",
        "run": "Construir paquete offline",
        "ready": "PACKAGE READY",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "summary": "Resumen del paquete",
        "diff_rows": "Filas diff",
        "review_rows": "Filas de revisión manual",
        "learning_rows": "Filas verificadas para learning",
        "manifest": "Descargar manifest JSON",
        "backup": "Descargar backup CSV",
        "updated": "Descargar CSV preview actualizado",
        "rollback": "Descargar rollback CSV",
        "audit": "Descargar audit JSON",
        "no_package": "Construye un paquete offline para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "package"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="offline_package_workspace_id"))

locked_csv = st.text_area(t("locked_csv"), value="", key="offline_package_locked_csv", height=160)
match_report_json = st.text_area(t("match_report_json"), value="", key="offline_package_match_report_json", height=160)
confirmation_json = st.text_area(t("confirmation_json"), value="", key="offline_package_confirmation_json", height=120)
value_json = st.text_area(t("value_json"), value="", key="offline_package_value_json", height=120)

if st.button(t("run"), key="offline_package_run"):
    st.session_state[PACKAGE_KEY] = build_offline_update_package_from_text(
        workspace_id,
        locked_csv,
        match_report_json,
        confirmation_json,
        value_json,
    )

package = st.session_state.get(PACKAGE_KEY, {})
if not package:
    st.info(t("no_package"))
    st.stop()

status = safe_text(package.get("status"))
status_key = "ready" if status == "PACKAGE READY" else "empty" if status == "NO ROWS" else "review"
st.write({t(status_key): True, t("preview_only"): bool(package.get("preview_only")), t("no_files"): int(package.get("files_written") or 0) == 0})

metrics = st.columns(6)
metrics[0].metric("status", status)
metrics[1].metric("locked", package.get("locked_row_count", 0))
metrics[2].metric("changed", package.get("changed_row_count", 0))
metrics[3].metric("review", package.get("manual_review_count", 0))
metrics[4].metric("learning", package.get("verified_learning_count", 0))
metrics[5].metric("hash", _fragment(package.get("package_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": package.get("schema_version"),
    "workspace_id": package.get("workspace_id"),
    "package_id": package.get("package_id"),
    "package_hash": package.get("package_hash"),
    "status": package.get("status"),
    "locked_row_count": package.get("locked_row_count"),
    "changed_row_count": package.get("changed_row_count"),
    "manual_review_count": package.get("manual_review_count"),
    "verified_learning_count": package.get("verified_learning_count"),
    "preview_only": package.get("preview_only"),
    "files_written": package.get("files_written"),
})

st.markdown(f"### {t('diff_rows')}")
st.dataframe(pd.DataFrame(package.get("diff_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('review_rows')}")
st.dataframe(pd.DataFrame(package.get("manual_review_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('learning_rows')}")
st.dataframe(pd.DataFrame(package.get("verified_learning_rows") or []), use_container_width=True, hide_index=True)

suffix = f"{safe_text(package.get('workspace_id'))}_{_fragment(package.get('package_hash'))}"
st.download_button(t("manifest"), export_package_manifest_json(package).encode("utf-8"), file_name=f"aba_offline_package_manifest_{suffix}.json", mime="application/json", key=f"offline_package_manifest_{safe_text(package.get('package_hash'))}")
st.download_button(t("backup"), safe_text(package.get("backup_csv")).encode("utf-8"), file_name=f"aba_offline_package_backup_{suffix}.csv", mime="text/csv", key=f"offline_package_backup_{safe_text(package.get('package_hash'))}")
st.download_button(t("updated"), safe_text(package.get("updated_csv_preview")).encode("utf-8"), file_name=f"aba_offline_package_updated_preview_{suffix}.csv", mime="text/csv", key=f"offline_package_updated_{safe_text(package.get('package_hash'))}")
st.download_button(t("rollback"), safe_text(package.get("rollback_csv")).encode("utf-8"), file_name=f"aba_offline_package_rollback_{suffix}.csv", mime="text/csv", key=f"offline_package_rollback_{safe_text(package.get('package_hash'))}")
st.download_button(t("audit"), safe_text(package.get("audit_json")).encode("utf-8"), file_name=f"aba_offline_package_audit_{suffix}.json", mime="application/json", key=f"offline_package_audit_{safe_text(package.get('package_hash'))}")

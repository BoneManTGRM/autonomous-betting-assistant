from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.canonical_store_recovery import (
    build_canonical_store_recovery_report_from_text,
    export_canonical_recovery_checks_csv,
    export_canonical_recovery_json,
    export_canonical_recovery_manifest_json,
    export_canonical_recovery_rows_csv,
    export_canonical_recovery_store_summaries_csv,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Canonical Store Recovery", layout="wide")
LANG = render_app_sidebar("canonical_store_recovery", language_key="canonical_store_recovery_language")

REPORT_KEY = "canonical_store_recovery_report"

TEXT = {
    "en": {
        "title": "Canonical Store Recovery",
        "caption": "Verify canonical proof recovery, save/reload consistency, and handoff safety without overwriting source data.",
        "workspace_id": "Workspace ID",
        "canonical_csv": "Canonical store rows CSV",
        "session_csv": "Session-state rows CSV",
        "disk_csv": "Disk fallback rows CSV",
        "local_json_csv": "Local JSON fallback rows CSV",
        "predictor_csv": "Pro Predictor rows CSV",
        "odds_lock_csv": "Odds Lock Pro rows CSV",
        "dashboard_csv": "Public Proof Dashboard rows CSV",
        "learning_csv": "Learning rows CSV",
        "reloaded_csv": "Reloaded verification rows CSV",
        "handoff_csv": "Page handoff inventory CSV",
        "metadata_json": "Optional metadata JSON",
        "run": "Run recovery check",
        "summary": "Recovery summary",
        "checks": "Recovery checks",
        "stores": "Store summaries",
        "recovered": "Recovered rows preview",
        "duplicates": "Duplicate proof ID groups",
        "workspace_mismatches": "Workspace mismatches",
        "safety": "Safety gates",
        "download_json": "Download recovery JSON",
        "download_checks": "Download checks CSV",
        "download_stores": "Download store summaries CSV",
        "download_rows": "Download recovered rows CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run the recovery check to view outputs.",
    },
    "es": {
        "title": "Canonical Store Recovery",
        "caption": "Verifica recuperación canonical proof, consistencia save/reload y seguridad de handoff sin sobrescribir datos fuente.",
        "workspace_id": "ID de workspace",
        "canonical_csv": "CSV filas canonical store",
        "session_csv": "CSV filas session-state",
        "disk_csv": "CSV filas disk fallback",
        "local_json_csv": "CSV filas local JSON fallback",
        "predictor_csv": "CSV filas Pro Predictor",
        "odds_lock_csv": "CSV filas Odds Lock Pro",
        "dashboard_csv": "CSV filas Public Proof Dashboard",
        "learning_csv": "CSV filas Learning",
        "reloaded_csv": "CSV filas reload verification",
        "handoff_csv": "CSV inventario de handoff de páginas",
        "metadata_json": "JSON metadata opcional",
        "run": "Ejecutar recovery check",
        "summary": "Resumen recovery",
        "checks": "Recovery checks",
        "stores": "Store summaries",
        "recovered": "Preview de filas recuperadas",
        "duplicates": "Grupos de proof ID duplicados",
        "workspace_mismatches": "Workspace mismatches",
        "safety": "Safety gates",
        "download_json": "Descargar JSON recovery",
        "download_checks": "Descargar CSV checks",
        "download_stores": "Descargar CSV store summaries",
        "download_rows": "Descargar CSV recovered rows",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta el recovery check para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "recovery"


st.title(t("title"))
st.caption(t("caption"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="canonical_recovery_workspace_id"))

canonical_csv = st.text_area(t("canonical_csv"), value="", key="canonical_recovery_canonical_csv", height=130)
session_csv = st.text_area(t("session_csv"), value="", key="canonical_recovery_session_csv", height=130)
disk_csv = st.text_area(t("disk_csv"), value="", key="canonical_recovery_disk_csv", height=130)
local_json_csv = st.text_area(t("local_json_csv"), value="", key="canonical_recovery_local_json_csv", height=120)
predictor_csv = st.text_area(t("predictor_csv"), value="", key="canonical_recovery_predictor_csv", height=120)
odds_lock_csv = st.text_area(t("odds_lock_csv"), value="", key="canonical_recovery_odds_lock_csv", height=120)
dashboard_csv = st.text_area(t("dashboard_csv"), value="", key="canonical_recovery_dashboard_csv", height=120)
learning_csv = st.text_area(t("learning_csv"), value="", key="canonical_recovery_learning_csv", height=120)
reloaded_csv = st.text_area(t("reloaded_csv"), value="", key="canonical_recovery_reloaded_csv", height=120)
handoff_csv = st.text_area(t("handoff_csv"), value="", key="canonical_recovery_handoff_csv", height=120)
metadata_json = st.text_area(t("metadata_json"), value="", key="canonical_recovery_metadata_json", height=100)

if st.button(t("run"), key="canonical_recovery_run"):
    st.session_state[REPORT_KEY] = build_canonical_store_recovery_report_from_text(
        workspace_id,
        canonical_csv,
        session_csv,
        disk_csv,
        local_json_csv,
        predictor_csv,
        odds_lock_csv,
        dashboard_csv,
        learning_csv,
        reloaded_csv,
        handoff_csv,
        metadata_json,
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("recovery_status", ""))
metrics[1].metric("source", report.get("resolved_store_name", ""))
metrics[2].metric("rows", report.get("resolved_row_count", 0))
metrics[3].metric("fallback", str(bool(report.get("recovered_from_fallback"))))
metrics[4].metric("deduped", report.get("duplicate_rows_removed", 0))
metrics[5].metric("warn", report.get("warn_count", 0))
metrics[6].metric("fail", report.get("fail_count", 0))
metrics[7].metric("hash", _fragment(report.get("recovery_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "recovery_id": report.get("recovery_id"),
    "recovery_hash": report.get("recovery_hash"),
    "mode": report.get("mode"),
    "recovery_status": report.get("recovery_status"),
    "resolved_store_name": report.get("resolved_store_name"),
    "resolution_status": report.get("resolution_status"),
    "resolved_row_count": report.get("resolved_row_count"),
    "raw_row_count": report.get("raw_row_count"),
    "recovered_from_fallback": report.get("recovered_from_fallback"),
    "duplicate_rows_removed": report.get("duplicate_rows_removed"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("recovery_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('stores')}")
st.dataframe(pd.DataFrame(report.get("store_summaries") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('recovered')}")
st.dataframe(pd.DataFrame(report.get("recovered_rows_preview") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('duplicates')}")
st.dataframe(pd.DataFrame(report.get("duplicate_proof_id_groups") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('workspace_mismatches')}")
st.dataframe(pd.DataFrame(report.get("workspace_mismatches") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('recovery_hash'))}"
st.download_button(t("download_json"), export_canonical_recovery_json(report).encode("utf-8"), file_name=f"aba_canonical_recovery_{suffix}.json", mime="application/json", key=f"canonical_recovery_json_{safe_text(report.get('recovery_hash'))}")
st.download_button(t("download_checks"), export_canonical_recovery_checks_csv(report).encode("utf-8"), file_name=f"aba_canonical_recovery_checks_{suffix}.csv", mime="text/csv", key=f"canonical_recovery_checks_{safe_text(report.get('recovery_hash'))}")
st.download_button(t("download_stores"), export_canonical_recovery_store_summaries_csv(report).encode("utf-8"), file_name=f"aba_canonical_recovery_stores_{suffix}.csv", mime="text/csv", key=f"canonical_recovery_stores_{safe_text(report.get('recovery_hash'))}")
st.download_button(t("download_rows"), export_canonical_recovery_rows_csv(report).encode("utf-8"), file_name=f"aba_canonical_recovery_rows_{suffix}.csv", mime="text/csv", key=f"canonical_recovery_rows_{safe_text(report.get('recovery_hash'))}")
st.download_button(t("download_manifest"), export_canonical_recovery_manifest_json(report).encode("utf-8"), file_name=f"aba_canonical_recovery_manifest_{suffix}.json", mime="application/json", key=f"canonical_recovery_manifest_{safe_text(report.get('recovery_hash'))}")

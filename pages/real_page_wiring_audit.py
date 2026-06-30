from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.real_page_wiring_audit import (
    build_real_page_wiring_audit_from_text,
    export_wiring_audit_json,
    export_wiring_checks_csv,
    export_wiring_manifest_json,
    export_wiring_page_summary_csv,
    export_wiring_risk_summary_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Real Page Wiring Audit", layout="wide")
LANG = render_app_sidebar("real_page_wiring_audit", language_key="real_page_wiring_audit_language")

REPORT_KEY = "real_page_wiring_audit_report"

TEXT = {
    "en": {
        "title": "Real Page Wiring Audit",
        "caption": "Check whether live pages are wired to canonical proof/recovery paths instead of isolated session copies.",
        "workspace_id": "Workspace ID",
        "page_inventory_csv": "Page inventory / source snippets CSV",
        "run": "Run wiring audit",
        "summary": "Wiring summary",
        "checks": "System checks",
        "pages": "Page results",
        "risks": "Risk summary",
        "actions": "Next actions",
        "safety": "Safety gates",
        "download_json": "Download wiring audit JSON",
        "download_pages": "Download page summary CSV",
        "download_risks": "Download risk summary CSV",
        "download_checks": "Download checks CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run the wiring audit to view outputs.",
    },
    "es": {
        "title": "Real Page Wiring Audit",
        "caption": "Verifica si las páginas reales usan proof/recovery canonical en lugar de copias aisladas de sesión.",
        "workspace_id": "ID de workspace",
        "page_inventory_csv": "CSV inventario de páginas / source snippets",
        "run": "Ejecutar wiring audit",
        "summary": "Resumen wiring",
        "checks": "System checks",
        "pages": "Resultados de páginas",
        "risks": "Resumen de riesgos",
        "actions": "Siguientes acciones",
        "safety": "Safety gates",
        "download_json": "Descargar JSON wiring audit",
        "download_pages": "Descargar CSV page summary",
        "download_risks": "Descargar CSV risk summary",
        "download_checks": "Descargar CSV checks",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta el wiring audit para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "wiring"


st.title(t("title"))
st.caption(t("caption"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="real_page_wiring_workspace_id"))
page_inventory_csv = st.text_area(t("page_inventory_csv"), value="", key="real_page_wiring_inventory_csv", height=260)

if st.button(t("run"), key="real_page_wiring_run"):
    st.session_state[REPORT_KEY] = build_real_page_wiring_audit_from_text(workspace_id, page_inventory_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("system_status", ""))
metrics[1].metric("pages", report.get("page_count", 0))
metrics[2].metric("wired", report.get("wired_count", 0))
metrics[3].metric("partial", report.get("partial_count", 0))
metrics[4].metric("review", report.get("review_required_count", 0))
metrics[5].metric("blocked", report.get("blocked_count", 0))
metrics[6].metric("warn", report.get("warn_count", 0))
metrics[7].metric("hash", _fragment(report.get("wiring_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "wiring_id": report.get("wiring_id"),
    "wiring_hash": report.get("wiring_hash"),
    "mode": report.get("mode"),
    "system_status": report.get("system_status"),
    "page_count": report.get("page_count"),
    "wired_count": report.get("wired_count"),
    "partial_count": report.get("partial_count"),
    "review_required_count": report.get("review_required_count"),
    "blocked_count": report.get("blocked_count"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("system_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('pages')}")
st.dataframe(pd.DataFrame(report.get("page_results") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('risks')}")
st.dataframe(pd.DataFrame(report.get("risk_summary") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('actions')}")
st.write(report.get("next_actions") or [])

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('wiring_hash'))}"
st.download_button(t("download_json"), export_wiring_audit_json(report).encode("utf-8"), file_name=f"aba_page_wiring_audit_{suffix}.json", mime="application/json", key=f"wiring_json_{safe_text(report.get('wiring_hash'))}")
st.download_button(t("download_pages"), export_wiring_page_summary_csv(report).encode("utf-8"), file_name=f"aba_page_wiring_pages_{suffix}.csv", mime="text/csv", key=f"wiring_pages_{safe_text(report.get('wiring_hash'))}")
st.download_button(t("download_risks"), export_wiring_risk_summary_csv(report).encode("utf-8"), file_name=f"aba_page_wiring_risks_{suffix}.csv", mime="text/csv", key=f"wiring_risks_{safe_text(report.get('wiring_hash'))}")
st.download_button(t("download_checks"), export_wiring_checks_csv(report).encode("utf-8"), file_name=f"aba_page_wiring_checks_{suffix}.csv", mime="text/csv", key=f"wiring_checks_{safe_text(report.get('wiring_hash'))}")
st.download_button(t("download_manifest"), export_wiring_manifest_json(report).encode("utf-8"), file_name=f"aba_page_wiring_manifest_{suffix}.json", mime="application/json", key=f"wiring_manifest_{safe_text(report.get('wiring_hash'))}")

from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.market_workflow_integration import (
    build_market_workflow_integration_from_text,
    export_flow_steps_csv,
    export_handoff_manifest_json,
    export_step_status_csv,
    export_workflow_checks_csv,
    export_workflow_integration_json,
    export_workflow_manifest_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Market Workflow Integration", layout="wide")
LANG = render_app_sidebar("market_workflow_integration", language_key="market_workflow_integration_language")

REPORT_KEY = "market_workflow_integration_report"

TEXT = {
    "en": {
        "title": "Market Workflow Integration",
        "caption": "Verify the preview workflow from Market Optimizer to Dashboard Bridge to proof/review tools.",
        "workspace_id": "Workspace ID",
        "optimizer_json": "Market Optimizer JSON",
        "bridge_json": "Market Dashboard Bridge JSON",
        "sidebar_text": "Sidebar/source text for navigation check",
        "page_inventory_csv": "Optional page inventory CSV",
        "run": "Verify workflow integration",
        "summary": "Workflow summary",
        "steps": "Flow steps",
        "step_status": "Step status",
        "checks": "Workflow checks",
        "actions": "Next actions",
        "handoff": "Handoff manifest",
        "safety": "Safety gates",
        "download_json": "Download workflow JSON",
        "download_steps": "Download flow steps CSV",
        "download_status": "Download step status CSV",
        "download_checks": "Download checks CSV",
        "download_handoff": "Download handoff manifest JSON",
        "download_manifest": "Download workflow manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Verify the workflow to view outputs.",
    },
    "es": {
        "title": "Market Workflow Integration",
        "caption": "Verifica el workflow preview de Market Optimizer a Dashboard Bridge y proof/review tools.",
        "workspace_id": "ID de workspace",
        "optimizer_json": "JSON Market Optimizer",
        "bridge_json": "JSON Market Dashboard Bridge",
        "sidebar_text": "Texto sidebar/source para navigation check",
        "page_inventory_csv": "CSV inventario de páginas opcional",
        "run": "Verificar workflow integration",
        "summary": "Resumen workflow",
        "steps": "Flow steps",
        "step_status": "Step status",
        "checks": "Workflow checks",
        "actions": "Siguientes acciones",
        "handoff": "Handoff manifest",
        "safety": "Safety gates",
        "download_json": "Descargar JSON workflow",
        "download_steps": "Descargar CSV flow steps",
        "download_status": "Descargar CSV step status",
        "download_checks": "Descargar CSV checks",
        "download_handoff": "Descargar JSON handoff manifest",
        "download_manifest": "Descargar JSON workflow manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Verifica el workflow para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "workflow"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="market_workflow_workspace_id"))
optimizer_json = st.text_area(t("optimizer_json"), value="", key="market_workflow_optimizer_json", height=180)
bridge_json = st.text_area(t("bridge_json"), value="", key="market_workflow_bridge_json", height=180)
sidebar_text = st.text_area(t("sidebar_text"), value="pages/market_optimizer.py pages/market_dashboard_bridge.py pages/market_workflow_integration.py pages/real_page_wiring_audit.py", key="market_workflow_sidebar_text", height=100)
page_inventory_csv = st.text_area(t("page_inventory_csv"), value="", key="market_workflow_page_inventory_csv", height=120)

if st.button(t("run"), key="market_workflow_run"):
    st.session_state[REPORT_KEY] = build_market_workflow_integration_from_text(workspace_id, optimizer_json, bridge_json, sidebar_text, page_inventory_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("workflow_status", ""))
metrics[1].metric("tracking", report.get("tracking_row_count", 0))
metrics[2].metric("handoff", report.get("handoff_row_count", 0))
metrics[3].metric("steps", len(report.get("flow_steps") or []))
metrics[4].metric("pass", report.get("pass_count", 0))
metrics[5].metric("warn", report.get("warn_count", 0))
metrics[6].metric("fail", report.get("fail_count", 0))
metrics[7].metric("hash", _fragment(report.get("workflow_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "workflow_id": report.get("workflow_id"),
    "workflow_hash": report.get("workflow_hash"),
    "mode": report.get("mode"),
    "workflow_status": report.get("workflow_status"),
    "optimizer_hash": report.get("optimizer_hash"),
    "bridge_hash": report.get("bridge_hash"),
    "tracking_row_count": report.get("tracking_row_count"),
    "handoff_row_count": report.get("handoff_row_count"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('steps')}")
st.dataframe(pd.DataFrame(report.get("flow_steps") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('step_status')}")
st.dataframe(pd.DataFrame(report.get("step_status_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("workflow_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('actions')}")
st.write(report.get("next_actions") or [])

st.markdown(f"### {t('handoff')}")
st.json(report.get("handoff_manifest") or {})

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('workflow_hash'))}"
st.download_button(t("download_json"), export_workflow_integration_json(report).encode("utf-8"), file_name=f"aba_market_workflow_{suffix}.json", mime="application/json", key=f"market_workflow_json_{safe_text(report.get('workflow_hash'))}")
st.download_button(t("download_steps"), export_flow_steps_csv(report).encode("utf-8"), file_name=f"aba_market_workflow_steps_{suffix}.csv", mime="text/csv", key=f"market_workflow_steps_{safe_text(report.get('workflow_hash'))}")
st.download_button(t("download_status"), export_step_status_csv(report).encode("utf-8"), file_name=f"aba_market_workflow_status_{suffix}.csv", mime="text/csv", key=f"market_workflow_status_{safe_text(report.get('workflow_hash'))}")
st.download_button(t("download_checks"), export_workflow_checks_csv(report).encode("utf-8"), file_name=f"aba_market_workflow_checks_{suffix}.csv", mime="text/csv", key=f"market_workflow_checks_{safe_text(report.get('workflow_hash'))}")
st.download_button(t("download_handoff"), export_handoff_manifest_json(report).encode("utf-8"), file_name=f"aba_market_workflow_handoff_{suffix}.json", mime="application/json", key=f"market_workflow_handoff_{safe_text(report.get('workflow_hash'))}")
st.download_button(t("download_manifest"), export_workflow_manifest_json(report).encode("utf-8"), file_name=f"aba_market_workflow_manifest_{suffix}.json", mime="application/json", key=f"market_workflow_manifest_{safe_text(report.get('workflow_hash'))}")

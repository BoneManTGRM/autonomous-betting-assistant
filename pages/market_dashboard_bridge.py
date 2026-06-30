from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.market_dashboard_bridge import (
    build_market_dashboard_bridge_from_text,
    export_dashboard_cards_json,
    export_market_bridge_checks_csv,
    export_market_bridge_json,
    export_market_bridge_manifest_json,
    export_proof_handoff_csv,
    export_segment_summary_csv,
    export_tracking_schema_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Market Dashboard Bridge", layout="wide")
LANG = render_app_sidebar("market_dashboard_bridge", language_key="market_dashboard_bridge_language")

REPORT_KEY = "market_dashboard_bridge_report"

TEXT = {
    "en": {
        "title": "Market Dashboard Bridge",
        "caption": "Convert Market Optimizer preview output into dashboard, tracking-schema, and proof-handoff exports.",
        "workspace_id": "Workspace ID",
        "optimizer_json": "Optimizer report JSON",
        "market_csv": "Optional Market Hunter rows CSV override",
        "chain_csv": "Optional Chain Builder rows CSV override",
        "avoid_csv": "Optional Avoid List rows CSV override",
        "run": "Build dashboard bridge",
        "summary": "Bridge summary",
        "cards": "Dashboard cards",
        "tracking": "Tracking schema rows",
        "segments": "Segment summary",
        "handoff": "Proof-flow handoff rows",
        "checks": "Bridge checks",
        "safety": "Safety gates",
        "download_json": "Download bridge JSON",
        "download_cards": "Download dashboard cards JSON",
        "download_tracking": "Download tracking schema CSV",
        "download_segments": "Download segment summary CSV",
        "download_handoff": "Download proof handoff CSV",
        "download_checks": "Download bridge checks CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Build the dashboard bridge to view outputs.",
    },
    "es": {
        "title": "Market Dashboard Bridge",
        "caption": "Convierte output del Market Optimizer preview en dashboard, tracking schema y proof-handoff exports.",
        "workspace_id": "ID de workspace",
        "optimizer_json": "JSON optimizer report",
        "market_csv": "CSV Market Hunter rows opcional",
        "chain_csv": "CSV Chain Builder rows opcional",
        "avoid_csv": "CSV Avoid List rows opcional",
        "run": "Construir dashboard bridge",
        "summary": "Resumen bridge",
        "cards": "Dashboard cards",
        "tracking": "Tracking schema rows",
        "segments": "Segment summary",
        "handoff": "Proof-flow handoff rows",
        "checks": "Bridge checks",
        "safety": "Safety gates",
        "download_json": "Descargar JSON bridge",
        "download_cards": "Descargar JSON dashboard cards",
        "download_tracking": "Descargar CSV tracking schema",
        "download_segments": "Descargar CSV segment summary",
        "download_handoff": "Descargar CSV proof handoff",
        "download_checks": "Descargar CSV bridge checks",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Construye el dashboard bridge para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "bridge"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="market_bridge_workspace_id"))
optimizer_json = st.text_area(t("optimizer_json"), value="", key="market_bridge_optimizer_json", height=220)
market_csv = st.text_area(t("market_csv"), value="", key="market_bridge_market_csv", height=150)
chain_csv = st.text_area(t("chain_csv"), value="", key="market_bridge_chain_csv", height=120)
avoid_csv = st.text_area(t("avoid_csv"), value="", key="market_bridge_avoid_csv", height=120)

if st.button(t("run"), key="market_bridge_run"):
    st.session_state[REPORT_KEY] = build_market_dashboard_bridge_from_text(workspace_id, optimizer_json, market_csv, chain_csv, avoid_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("bridge_status", ""))
metrics[1].metric("markets", report.get("market_row_count", 0))
metrics[2].metric("tracking", report.get("tracking_row_count", 0))
metrics[3].metric("chains", report.get("chain_row_count", 0))
metrics[4].metric("avoid", report.get("avoid_row_count", 0))
metrics[5].metric("warn", report.get("warn_count", 0))
metrics[6].metric("fail", report.get("fail_count", 0))
metrics[7].metric("hash", _fragment(report.get("bridge_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "tracking_schema_version": report.get("tracking_schema_version"),
    "workspace_id": report.get("workspace_id"),
    "bridge_id": report.get("bridge_id"),
    "bridge_hash": report.get("bridge_hash"),
    "mode": report.get("mode"),
    "bridge_status": report.get("bridge_status"),
    "tracking_row_count": report.get("tracking_row_count"),
    "market_row_count": report.get("market_row_count"),
    "chain_row_count": report.get("chain_row_count"),
    "avoid_row_count": report.get("avoid_row_count"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('cards')}")
st.json(report.get("dashboard_cards") or {})

st.markdown(f"### {t('tracking')}")
st.dataframe(pd.DataFrame(report.get("tracking_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('segments')}")
st.dataframe(pd.DataFrame(report.get("segment_summary_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('handoff')}")
st.dataframe(pd.DataFrame(report.get("proof_handoff_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("bridge_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('bridge_hash'))}"
st.download_button(t("download_json"), export_market_bridge_json(report).encode("utf-8"), file_name=f"aba_market_bridge_{suffix}.json", mime="application/json", key=f"market_bridge_json_{safe_text(report.get('bridge_hash'))}")
st.download_button(t("download_cards"), export_dashboard_cards_json(report).encode("utf-8"), file_name=f"aba_market_dashboard_cards_{suffix}.json", mime="application/json", key=f"market_bridge_cards_{safe_text(report.get('bridge_hash'))}")
st.download_button(t("download_tracking"), export_tracking_schema_csv(report).encode("utf-8"), file_name=f"aba_market_tracking_{suffix}.csv", mime="text/csv", key=f"market_bridge_tracking_{safe_text(report.get('bridge_hash'))}")
st.download_button(t("download_segments"), export_segment_summary_csv(report).encode("utf-8"), file_name=f"aba_market_segments_{suffix}.csv", mime="text/csv", key=f"market_bridge_segments_{safe_text(report.get('bridge_hash'))}")
st.download_button(t("download_handoff"), export_proof_handoff_csv(report).encode("utf-8"), file_name=f"aba_market_proof_handoff_{suffix}.csv", mime="text/csv", key=f"market_bridge_handoff_{safe_text(report.get('bridge_hash'))}")
st.download_button(t("download_checks"), export_market_bridge_checks_csv(report).encode("utf-8"), file_name=f"aba_market_bridge_checks_{suffix}.csv", mime="text/csv", key=f"market_bridge_checks_{safe_text(report.get('bridge_hash'))}")
st.download_button(t("download_manifest"), export_market_bridge_manifest_json(report).encode("utf-8"), file_name=f"aba_market_bridge_manifest_{suffix}.json", mime="application/json", key=f"market_bridge_manifest_{safe_text(report.get('bridge_hash'))}")

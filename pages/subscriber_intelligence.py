from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.subscriber_intelligence import (
    build_subscriber_intelligence_from_text,
    export_admin_summary_json,
    export_personalized_rows_csv,
    export_profiles_csv,
    export_subscriber_checks_csv,
    export_subscriber_intelligence_json,
    export_subscriber_manifest_json,
    export_subscriber_reports_json,
)

st.set_page_config(page_title="Subscriber Intelligence", layout="wide")
LANG = render_app_sidebar("subscriber_intelligence", language_key="subscriber_intelligence_language")

REPORT_KEY = "subscriber_intelligence_report"

TEXT = {
    "en": {
        "title": "Subscriber Intelligence",
        "caption": "Preview subscriber-specific recommendations from one shared market pool without billing, key exposure, or live actions.",
        "workspace_id": "Workspace ID",
        "profiles_csv": "Subscriber profiles CSV",
        "optimizer_json": "Optional Market Optimizer JSON",
        "market_csv": "Optional Market rows CSV override",
        "run": "Build subscriber reports",
        "summary": "Subscriber summary",
        "admin": "Admin summary",
        "profiles": "Profiles",
        "rows": "Personalized rows",
        "reports": "Subscriber reports",
        "checks": "Checks",
        "safety": "Safety gates",
        "download_json": "Download subscriber JSON",
        "download_profiles": "Download profiles CSV",
        "download_rows": "Download personalized rows CSV",
        "download_reports": "Download subscriber reports JSON",
        "download_admin": "Download admin summary JSON",
        "download_checks": "Download checks CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Build subscriber reports to view outputs.",
    },
    "es": {
        "title": "Subscriber Intelligence",
        "caption": "Genera recomendaciones por subscriber desde un pool compartido sin billing, exposición de keys o acciones live.",
        "workspace_id": "ID de workspace",
        "profiles_csv": "CSV perfiles de subscriber",
        "optimizer_json": "JSON Market Optimizer opcional",
        "market_csv": "CSV market rows opcional",
        "run": "Construir reportes subscriber",
        "summary": "Resumen subscriber",
        "admin": "Resumen admin",
        "profiles": "Perfiles",
        "rows": "Filas personalizadas",
        "reports": "Reportes subscriber",
        "checks": "Checks",
        "safety": "Safety gates",
        "download_json": "Descargar JSON subscriber",
        "download_profiles": "Descargar CSV perfiles",
        "download_rows": "Descargar CSV filas personalizadas",
        "download_reports": "Descargar JSON reportes subscriber",
        "download_admin": "Descargar JSON resumen admin",
        "download_checks": "Descargar CSV checks",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Construye reportes subscriber para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "subscriber"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="subscriber_intelligence_workspace_id"))
profiles_csv = st.text_area(t("profiles_csv"), value="", key="subscriber_intelligence_profiles_csv", height=200)
optimizer_json = st.text_area(t("optimizer_json"), value="", key="subscriber_intelligence_optimizer_json", height=160)
market_csv = st.text_area(t("market_csv"), value="", key="subscriber_intelligence_market_csv", height=180)

if st.button(t("run"), key="subscriber_intelligence_run"):
    st.session_state[REPORT_KEY] = build_subscriber_intelligence_from_text(workspace_id, profiles_csv, optimizer_json, market_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("subscriber_status", ""))
metrics[1].metric("subscribers", report.get("subscriber_count", 0))
metrics[2].metric("enabled", report.get("enabled_subscriber_count", 0))
metrics[3].metric("markets", report.get("market_row_count", 0))
metrics[4].metric("bet rows", report.get("admin_summary", {}).get("total_bet_recommendations", 0))
metrics[5].metric("no bet", report.get("admin_summary", {}).get("total_no_bet_rows", 0))
metrics[6].metric("fail", report.get("fail_count", 0))
metrics[7].metric("hash", _fragment(report.get("subscriber_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "subscriber_run_id": report.get("subscriber_run_id"),
    "subscriber_hash": report.get("subscriber_hash"),
    "mode": report.get("mode"),
    "subscriber_status": report.get("subscriber_status"),
    "subscriber_count": report.get("subscriber_count"),
    "enabled_subscriber_count": report.get("enabled_subscriber_count"),
    "market_row_count": report.get("market_row_count"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('admin')}")
st.json(report.get("admin_summary") or {})

st.markdown(f"### {t('profiles')}")
st.dataframe(pd.DataFrame(report.get("profiles") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('rows')}")
st.dataframe(pd.DataFrame(report.get("personalized_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('reports')}")
st.json(report.get("subscriber_reports") or [])

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("subscriber_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('subscriber_hash'))}"
st.download_button(t("download_json"), export_subscriber_intelligence_json(report).encode("utf-8"), file_name=f"aba_subscriber_intelligence_{suffix}.json", mime="application/json", key=f"subscriber_intelligence_json_{safe_text(report.get('subscriber_hash'))}")
st.download_button(t("download_profiles"), export_profiles_csv(report).encode("utf-8"), file_name=f"aba_subscriber_profiles_{suffix}.csv", mime="text/csv", key=f"subscriber_profiles_csv_{safe_text(report.get('subscriber_hash'))}")
st.download_button(t("download_rows"), export_personalized_rows_csv(report).encode("utf-8"), file_name=f"aba_subscriber_rows_{suffix}.csv", mime="text/csv", key=f"subscriber_rows_csv_{safe_text(report.get('subscriber_hash'))}")
st.download_button(t("download_reports"), export_subscriber_reports_json(report).encode("utf-8"), file_name=f"aba_subscriber_reports_{suffix}.json", mime="application/json", key=f"subscriber_reports_json_{safe_text(report.get('subscriber_hash'))}")
st.download_button(t("download_admin"), export_admin_summary_json(report).encode("utf-8"), file_name=f"aba_subscriber_admin_{suffix}.json", mime="application/json", key=f"subscriber_admin_json_{safe_text(report.get('subscriber_hash'))}")
st.download_button(t("download_checks"), export_subscriber_checks_csv(report).encode("utf-8"), file_name=f"aba_subscriber_checks_{suffix}.csv", mime="text/csv", key=f"subscriber_checks_csv_{safe_text(report.get('subscriber_hash'))}")
st.download_button(t("download_manifest"), export_subscriber_manifest_json(report).encode("utf-8"), file_name=f"aba_subscriber_manifest_{suffix}.json", mime="application/json", key=f"subscriber_manifest_json_{safe_text(report.get('subscriber_hash'))}")

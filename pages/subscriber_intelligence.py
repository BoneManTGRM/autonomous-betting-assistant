from __future__ import annotations

import json

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
PROFILE_TEMPLATE = "subscriber_id,subscriber_name,plan,risk_tolerance,preferred_sports,enabled\ndefault,Default Subscriber,standard,medium,,true\n"

TEXT = {
    "en": {
        "title": "Subscriber Intelligence",
        "caption": "Creates subscriber-specific previews from the latest market optimizer result.",
        "help": "Use this only when you are preparing subscriber reports. For normal prediction tracking, stay in Pro Predictor, Odds Lock Pro, and Proof Center.",
        "workspace_id": "Workspace ID",
        "source": "Source check",
        "profiles": "Subscriber setup",
        "template": "Use simple default subscriber template",
        "run": "Build subscriber preview",
        "advanced": "Advanced manual input",
        "profiles_csv": "Subscriber profiles CSV",
        "optimizer_json": "Manual Market Optimizer JSON",
        "market_csv": "Optional manual market rows CSV",
        "summary": "Summary",
        "admin": "Admin view",
        "rows": "Personalized rows",
        "reports": "Subscriber reports",
        "checks": "Checks",
        "safety": "Safety details",
        "no_report": "Build subscriber preview to view outputs.",
        "no_source": "No Market Optimizer result found. Run Market Optimizer first or paste JSON in Advanced.",
    },
    "es": {
        "title": "Inteligencia de Subscribers",
        "caption": "Crea previews por subscriber desde el último resultado de Market Optimizer.",
        "help": "Usa esto solo para preparar reportes de subscribers. Para tracking normal usa Predictor Pro, Odds Lock Pro y Proof Center.",
        "workspace_id": "ID de workspace",
        "source": "Revisión de fuente",
        "profiles": "Configuración de subscriber",
        "template": "Usar template simple de subscriber",
        "run": "Construir preview subscriber",
        "advanced": "Entrada manual avanzada",
        "profiles_csv": "CSV perfiles subscriber",
        "optimizer_json": "JSON manual Market Optimizer",
        "market_csv": "CSV manual opcional de mercado",
        "summary": "Resumen",
        "admin": "Vista admin",
        "rows": "Filas personalizadas",
        "reports": "Reportes subscriber",
        "checks": "Checks",
        "safety": "Detalles de seguridad",
        "no_report": "Construye preview subscriber para ver outputs.",
        "no_source": "No hay resultado de Market Optimizer. Ejecútalo primero o pega JSON en Avanzado.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "subscriber"


def _session_json(key: str) -> tuple[str, int]:
    value = st.session_state.get(key) or {}
    if not value:
        return "", 0
    try:
        return json.dumps(value), 1
    except Exception:
        return "", 0


st.title(t("title"))
st.caption(t("caption"))
st.info(t("help"))

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="subscriber_intelligence_workspace_id"))
auto_optimizer_json, optimizer_found = _session_json("market_optimizer_preview_report")

st.subheader(t("source"))
cols = st.columns(2)
cols[0].metric("Market Optimizer result", "found" if optimizer_found else "missing")
cols[1].metric("workspace", workspace_id)
if not optimizer_found:
    st.warning(t("no_source"))

st.subheader(t("profiles"))
use_template = st.checkbox(t("template"), value=True, key="subscriber_use_default_template")

with st.expander(t("advanced"), expanded=False):
    profiles_csv = st.text_area(t("profiles_csv"), value=PROFILE_TEMPLATE if use_template else "", key="subscriber_intelligence_profiles_csv", height=160)
    optimizer_json = st.text_area(t("optimizer_json"), value=auto_optimizer_json, key="subscriber_intelligence_optimizer_json", height=160)
    market_csv = st.text_area(t("market_csv"), value="", key="subscriber_intelligence_market_csv", height=160)

if st.button(t("run"), key="subscriber_intelligence_run", type="primary"):
    profile_text = profiles_csv or (PROFILE_TEMPLATE if use_template else "")
    st.session_state[REPORT_KEY] = build_subscriber_intelligence_from_text(workspace_id, profile_text, optimizer_json or auto_optimizer_json, market_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

metrics = st.columns(7)
metrics[0].metric("status", report.get("subscriber_status", ""))
metrics[1].metric("subscribers", report.get("subscriber_count", 0))
metrics[2].metric("enabled", report.get("enabled_subscriber_count", 0))
metrics[3].metric("markets", report.get("market_row_count", 0))
metrics[4].metric("bet rows", report.get("admin_summary", {}).get("total_bet_recommendations", 0))
metrics[5].metric("no bet", report.get("admin_summary", {}).get("total_no_bet_rows", 0))
metrics[6].metric("fail", report.get("fail_count", 0))

tabs = st.tabs([t("summary"), t("admin"), t("rows"), t("reports"), t("checks")])
with tabs[0]:
    st.json({
        "workspace_id": report.get("workspace_id"),
        "subscriber_status": report.get("subscriber_status"),
        "subscriber_count": report.get("subscriber_count"),
        "enabled_subscriber_count": report.get("enabled_subscriber_count"),
        "market_row_count": report.get("market_row_count"),
        "preview_only": report.get("preview_only"),
        "live_changes": report.get("live_changes"),
    })
with tabs[1]:
    st.json(report.get("admin_summary") or {})
with tabs[2]:
    st.dataframe(pd.DataFrame(report.get("personalized_rows") or []), use_container_width=True, hide_index=True)
with tabs[3]:
    st.json(report.get("subscriber_reports") or [])
with tabs[4]:
    st.dataframe(pd.DataFrame(report.get("subscriber_checks") or []), use_container_width=True, hide_index=True)

with st.expander(t("safety"), expanded=False):
    st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('subscriber_hash'))}"
st.download_button("Download subscriber JSON", export_subscriber_intelligence_json(report).encode("utf-8"), file_name=f"aba_subscriber_intelligence_{suffix}.json", mime="application/json", key=f"subscriber_intelligence_json_{safe_text(report.get('subscriber_hash'))}")
st.download_button("Download profiles CSV", export_profiles_csv(report).encode("utf-8"), file_name=f"aba_subscriber_profiles_{suffix}.csv", mime="text/csv", key=f"subscriber_profiles_csv_{safe_text(report.get('subscriber_hash'))}")
st.download_button("Download personalized rows CSV", export_personalized_rows_csv(report).encode("utf-8"), file_name=f"aba_subscriber_rows_{suffix}.csv", mime="text/csv", key=f"subscriber_rows_csv_{safe_text(report.get('subscriber_hash'))}")
st.download_button("Download reports JSON", export_subscriber_reports_json(report).encode("utf-8"), file_name=f"aba_subscriber_reports_{suffix}.json", mime="application/json", key=f"subscriber_reports_json_{safe_text(report.get('subscriber_hash'))}")
st.download_button("Download admin JSON", export_admin_summary_json(report).encode("utf-8"), file_name=f"aba_subscriber_admin_{suffix}.json", mime="application/json", key=f"subscriber_admin_json_{safe_text(report.get('subscriber_hash'))}")
st.download_button("Download checks CSV", export_subscriber_checks_csv(report).encode("utf-8"), file_name=f"aba_subscriber_checks_{suffix}.csv", mime="text/csv", key=f"subscriber_checks_csv_{safe_text(report.get('subscriber_hash'))}")
st.download_button("Download manifest JSON", export_subscriber_manifest_json(report).encode("utf-8"), file_name=f"aba_subscriber_manifest_{suffix}.json", mime="application/json", key=f"subscriber_manifest_json_{safe_text(report.get('subscriber_hash'))}")

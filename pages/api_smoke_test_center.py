from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.api_smoke_test_service import (
    build_api_smoke_report,
    export_api_smoke_report_json,
    parse_json_payload,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="API Smoke Test Center", layout="wide")
LANG = render_app_sidebar("api_smoke_test_center", language_key="api_smoke_test_language")

REPORT_KEY = "api_smoke_test_report"

TEXT = {
    "en": {
        "title": "API Smoke Test Center",
        "caption": "Safe readiness checks for API keys, redacted request plans, response shapes, and proof-safe diagnostics.",
        "workspace_id": "Workspace ID",
        "odds_response": "The Odds API sample response JSON",
        "sportsdata_response": "SportsDataIO sample response JSON",
        "weather_response": "WeatherAPI sample response JSON",
        "run": "Run API smoke test",
        "ready": "API READY",
        "review": "REVIEW REQUIRED",
        "missing": "MISSING KEYS",
        "empty": "NO SAMPLE RESPONSE",
        "preview_only": "PREVIEW ONLY",
        "proof_safe": "NO PROOF ROWS CHANGED",
        "summary": "Smoke summary",
        "keys": "Key readiness",
        "plans": "Redacted request plans",
        "payloads": "Payload analysis",
        "download": "Download API smoke JSON",
        "no_report": "Run API smoke test to view readiness details.",
    },
    "es": {
        "title": "Centro de Prueba Smoke API",
        "caption": "Revisiones seguras para API keys, planes redactados, formas de respuesta y diagnosticos seguros para proof.",
        "workspace_id": "ID de workspace",
        "odds_response": "JSON de respuesta muestra The Odds API",
        "sportsdata_response": "JSON de respuesta muestra SportsDataIO",
        "weather_response": "JSON de respuesta muestra WeatherAPI",
        "run": "Ejecutar prueba smoke API",
        "ready": "API READY",
        "review": "REVIEW REQUIRED",
        "missing": "MISSING KEYS",
        "empty": "NO SAMPLE RESPONSE",
        "preview_only": "PREVIEW ONLY",
        "proof_safe": "NO PROOF ROWS CHANGED",
        "summary": "Resumen smoke",
        "keys": "Estado de keys",
        "plans": "Planes de request redactados",
        "payloads": "Analisis de payload",
        "download": "Descargar JSON smoke API",
        "no_report": "Ejecuta la prueba smoke API para ver detalles.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "smoke"


def _safe_secrets() -> dict[str, str]:
    names = ("ODDS_API_KEY", "THE_ODDS_API_KEY", "SPORTSDATAIO_API_KEY", "SPORTS_DATA_IO_API_KEY", "WEATHERAPI_KEY", "WEATHER_API_KEY")
    return {name: str(st.secrets.get(name, "")) for name in names if str(st.secrets.get(name, ""))}


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="api_smoke_workspace_id"))

odds_response = st.text_area(t("odds_response"), value="", key="api_smoke_odds_response", height=140)
sportsdata_response = st.text_area(t("sportsdata_response"), value="", key="api_smoke_sportsdata_response", height=140)
weather_response = st.text_area(t("weather_response"), value="", key="api_smoke_weather_response", height=140)

if st.button(t("run"), key="api_smoke_run"):
    st.session_state[REPORT_KEY] = build_api_smoke_report(
        workspace_id,
        _safe_secrets(),
        {
            "the_odds_api": parse_json_payload(odds_response),
            "sportsdataio": parse_json_payload(sportsdata_response),
            "weatherapi": parse_json_payload(weather_response),
        },
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

status_key = "ready" if report.get("status") == "API READY" else "missing" if report.get("status") == "MISSING KEYS" else "empty" if report.get("status") == "NO SAMPLE RESPONSE" else "review"
st.write({t(status_key): True, t("preview_only"): bool(report.get("preview_only")), t("proof_safe"): int(report.get("proof_rows_changed") or 0) == 0})

metrics = st.columns(6)
metrics[0].metric("status", safe_text(report.get("status")))
metrics[1].metric("ready", report.get("ready_provider_count", 0))
metrics[2].metric("review", report.get("review_provider_count", 0))
metrics[3].metric("missing_keys", report.get("missing_key_count", 0))
metrics[4].metric("no_sample", report.get("no_sample_count", 0))
metrics[5].metric("changed", report.get("proof_rows_changed", 0))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "status": report.get("status"),
    "ready_provider_count": report.get("ready_provider_count"),
    "review_provider_count": report.get("review_provider_count"),
    "missing_key_count": report.get("missing_key_count"),
    "no_sample_count": report.get("no_sample_count"),
    "preview_only": report.get("preview_only"),
    "proof_rows_changed": report.get("proof_rows_changed"),
})

st.markdown(f"### {t('keys')}")
st.dataframe(pd.DataFrame(report.get("key_readiness") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('plans')}")
st.json(report.get("request_plans") or [])

st.markdown(f"### {t('payloads')}")
st.dataframe(pd.DataFrame(report.get("payload_analysis") or []), use_container_width=True, hide_index=True)

st.download_button(
    t("download"),
    export_api_smoke_report_json(report).encode("utf-8"),
    file_name=f"aba_api_smoke_{safe_text(report.get('workspace_id'))}_{_fragment(report.get('status'))}.json",
    mime="application/json",
    key=f"api_smoke_json_{safe_text(report.get('status'))}",
)

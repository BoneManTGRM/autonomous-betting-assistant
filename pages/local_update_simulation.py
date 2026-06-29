from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.local_update_simulation import (
    build_local_update_simulation_from_text,
    export_simulation_manifest_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="End-to-End Local Update Simulation", layout="wide")
LANG = render_app_sidebar("local_update_simulation", language_key="local_update_simulation_language")

REPORT_KEY = "local_update_simulation_report"

TEXT = {
    "en": {
        "title": "End-to-End Local Update Simulation",
        "caption": "Run the no-server local flow from API smoke payloads through matching, package building, and adaptive intake.",
        "workspace_id": "Workspace ID",
        "locked_csv": "Locked proof CSV",
        "provider_events": "Provider events JSON",
        "confirmation_json": "Confirmation payload JSON",
        "value_json": "Value payload JSON",
        "odds_payload": "The Odds API sample payload JSON",
        "sportsdata_payload": "SportsDataIO sample payload JSON",
        "weather_payload": "WeatherAPI sample payload JSON",
        "shadow_csv": "Optional shadow-learning CSV",
        "review_json": "Optional review rows JSON",
        "match_threshold": "Match threshold",
        "review_threshold": "Review threshold",
        "verified_confidence": "Verified confidence threshold",
        "intake_review_confidence": "Intake review confidence threshold",
        "run": "Run local simulation",
        "ready": "SIMULATION READY",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "safe": "NO PROOF ROWS CHANGED",
        "summary": "Simulation summary",
        "smoke": "API smoke summary",
        "match": "Match report summary",
        "package": "Offline package summary",
        "intake": "Adaptive intake summary",
        "flags": "Review flags",
        "download": "Download simulation manifest JSON",
        "no_report": "Run the local simulation to view the full no-server flow.",
    },
    "es": {
        "title": "Simulación Local End-to-End",
        "caption": "Ejecuta el flujo local sin servidor desde payloads API smoke hasta matching, paquete e intake adaptativo.",
        "workspace_id": "ID de workspace",
        "locked_csv": "CSV proof bloqueado",
        "provider_events": "JSON de eventos del proveedor",
        "confirmation_json": "JSON de payload de confirmación",
        "value_json": "JSON de payload de valor",
        "odds_payload": "JSON payload muestra The Odds API",
        "sportsdata_payload": "JSON payload muestra SportsDataIO",
        "weather_payload": "JSON payload muestra WeatherAPI",
        "shadow_csv": "CSV opcional para shadow learning",
        "review_json": "JSON opcional de filas review",
        "match_threshold": "Umbral de match",
        "review_threshold": "Umbral de review",
        "verified_confidence": "Umbral de confianza verified",
        "intake_review_confidence": "Umbral de confianza review intake",
        "run": "Ejecutar simulación local",
        "ready": "SIMULATION READY",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "safe": "NO PROOF ROWS CHANGED",
        "summary": "Resumen de simulación",
        "smoke": "Resumen API smoke",
        "match": "Resumen match",
        "package": "Resumen paquete offline",
        "intake": "Resumen intake adaptativo",
        "flags": "Flags de revisión",
        "download": "Descargar manifest JSON de simulación",
        "no_report": "Ejecuta la simulación local para ver el flujo sin servidor.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "sim"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="local_sim_workspace_id"))

cols = st.columns(4)
match_threshold = cols[0].number_input(t("match_threshold"), min_value=0.50, max_value=1.0, value=0.82, step=0.01, key="local_sim_match_threshold")
review_threshold = cols[1].number_input(t("review_threshold"), min_value=0.30, max_value=0.95, value=0.68, step=0.01, key="local_sim_review_threshold")
verified_confidence = cols[2].number_input(t("verified_confidence"), min_value=0.50, max_value=1.0, value=0.82, step=0.01, key="local_sim_verified_confidence")
intake_review_confidence = cols[3].number_input(t("intake_review_confidence"), min_value=0.10, max_value=0.95, value=0.50, step=0.01, key="local_sim_intake_review_confidence")

locked_csv = st.text_area(t("locked_csv"), value="", key="local_sim_locked_csv", height=140)
provider_events = st.text_area(t("provider_events"), value="", key="local_sim_provider_events", height=140)
confirmation_json = st.text_area(t("confirmation_json"), value="", key="local_sim_confirmation_json", height=110)
value_json = st.text_area(t("value_json"), value="", key="local_sim_value_json", height=110)

api_cols = st.columns(3)
odds_payload = api_cols[0].text_area(t("odds_payload"), value="", key="local_sim_odds_payload", height=140)
sportsdata_payload = api_cols[1].text_area(t("sportsdata_payload"), value="", key="local_sim_sportsdata_payload", height=140)
weather_payload = api_cols[2].text_area(t("weather_payload"), value="", key="local_sim_weather_payload", height=140)

shadow_csv = st.text_area(t("shadow_csv"), value="", key="local_sim_shadow_csv", height=100)
review_json = st.text_area(t("review_json"), value="", key="local_sim_review_json", height=100)

if st.button(t("run"), key="local_sim_run"):
    st.session_state[REPORT_KEY] = build_local_update_simulation_from_text(
        workspace_id,
        locked_csv,
        provider_events,
        confirmation_json,
        value_json,
        odds_payload,
        sportsdata_payload,
        weather_payload,
        shadow_csv,
        review_json,
        match_threshold=float(match_threshold),
        review_threshold=float(review_threshold),
        verified_confidence=float(verified_confidence),
        review_confidence=float(intake_review_confidence),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

status = safe_text(report.get("status"))
status_key = "ready" if status == "SIMULATION READY" else "empty" if status == "NO ROWS" else "review"
st.write({t(status_key): True, t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("safe"): int(report.get("proof_rows_changed") or 0) == 0})

metrics = st.columns(8)
metrics[0].metric("status", status)
metrics[1].metric("locked", report.get("locked_row_count", 0))
metrics[2].metric("providers", report.get("ready_provider_count", 0))
metrics[3].metric("matched", report.get("matched_count", 0))
metrics[4].metric("package", report.get("package_changed_count", 0))
metrics[5].metric("verified", report.get("intake_verified_count", 0))
metrics[6].metric("review", report.get("intake_review_count", 0))
metrics[7].metric("hash", _fragment(report.get("simulation_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "simulation_id": report.get("simulation_id"),
    "simulation_hash": report.get("simulation_hash"),
    "status": report.get("status"),
    "locked_row_count": report.get("locked_row_count"),
    "provider_event_count": report.get("provider_event_count"),
    "ready_provider_count": report.get("ready_provider_count"),
    "matched_count": report.get("matched_count"),
    "package_changed_count": report.get("package_changed_count"),
    "intake_verified_count": report.get("intake_verified_count"),
    "intake_review_count": report.get("intake_review_count"),
    "intake_shadow_count": report.get("intake_shadow_count"),
    "intake_quarantine_count": report.get("intake_quarantine_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "proof_rows_changed": report.get("proof_rows_changed"),
})

st.markdown(f"### {t('flags')}")
st.dataframe(pd.DataFrame([{"flag": item} for item in report.get("review_flags") or []]), use_container_width=True, hide_index=True)

st.markdown(f"### {t('smoke')}")
st.json(report.get("smoke_summary") or {})

st.markdown(f"### {t('match')}")
st.json({key: value for key, value in dict(report.get("match_report") or {}).items() if key != "match_rows"})

st.markdown(f"### {t('package')}")
st.json({key: value for key, value in dict(report.get("offline_package") or {}).items() if key not in {"backup_csv", "updated_csv_preview", "rollback_csv", "diff_rows", "manual_review_rows", "verified_learning_rows"}})

st.markdown(f"### {t('intake')}")
st.json({key: value for key, value in dict(report.get("adaptive_intake") or {}).items() if key != "lane_rows"})

st.download_button(
    t("download"),
    export_simulation_manifest_json(report).encode("utf-8"),
    file_name=f"aba_local_update_simulation_{safe_text(report.get('workspace_id'))}_{_fragment(report.get('simulation_hash'))}.json",
    mime="application/json",
    key=f"local_update_sim_manifest_{safe_text(report.get('simulation_hash'))}",
)

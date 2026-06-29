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

st.set_page_config(page_title="Local Update Simulation", layout="wide")
LANG = render_app_sidebar("local_update_simulation", language_key="local_update_simulation_language")

REPORT_KEY = "local_update_simulation_report"

TEXT = {
    "en": {
        "title": "Local Update Simulation",
        "caption": "Run the no-server chain: API Smoke, Event Match, Offline Package, and Adaptive Intake.",
        "workspace_id": "Workspace ID",
        "locked_csv": "Locked proof CSV",
        "provider_json": "Provider events JSON",
        "confirmation_json": "Confirmation payload JSON",
        "value_json": "Value payload JSON",
        "shadow_csv": "Optional shadow CSV",
        "review_json": "Optional review JSON",
        "match_threshold": "Match threshold",
        "review_threshold": "Match review threshold",
        "verified_confidence": "Verified confidence threshold",
        "intake_review_confidence": "Intake review threshold",
        "run": "Run local simulation",
        "ready": "SIMULATION READY",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "summary": "Simulation summary",
        "stages": "Stage summary",
        "downloads": "Downloads",
        "manifest": "Download simulation manifest JSON",
        "download": "Download artifact",
        "no_report": "Run the local simulation to view outputs.",
    },
    "es": {
        "title": "Simulación Local de Actualización",
        "caption": "Ejecuta la cadena sin servidor: API Smoke, Event Match, Offline Package y Adaptive Intake.",
        "workspace_id": "ID de workspace",
        "locked_csv": "CSV proof bloqueado",
        "provider_json": "JSON de eventos del proveedor",
        "confirmation_json": "JSON de payload de confirmación",
        "value_json": "JSON de payload de valor",
        "shadow_csv": "CSV shadow opcional",
        "review_json": "JSON review opcional",
        "match_threshold": "Umbral de match",
        "review_threshold": "Umbral de revisión match",
        "verified_confidence": "Umbral de confianza verified",
        "intake_review_confidence": "Umbral de revisión intake",
        "run": "Ejecutar simulación local",
        "ready": "SIMULATION READY",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "summary": "Resumen de simulación",
        "stages": "Resumen de etapas",
        "downloads": "Descargas",
        "manifest": "Descargar manifest JSON de simulación",
        "download": "Descargar artefacto",
        "no_report": "Ejecuta la simulación local para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "simulation"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="local_sim_workspace_id"))

cols = st.columns(4)
match_threshold = cols[0].number_input(t("match_threshold"), min_value=0.50, max_value=1.0, value=0.82, step=0.01, key="local_sim_match_threshold")
review_threshold = cols[1].number_input(t("review_threshold"), min_value=0.30, max_value=0.95, value=0.68, step=0.01, key="local_sim_review_threshold")
verified_confidence = cols[2].number_input(t("verified_confidence"), min_value=0.50, max_value=1.0, value=0.82, step=0.01, key="local_sim_verified_confidence")
intake_review_confidence = cols[3].number_input(t("intake_review_confidence"), min_value=0.10, max_value=0.95, value=0.50, step=0.01, key="local_sim_intake_review_confidence")

locked_csv = st.text_area(t("locked_csv"), value="", key="local_sim_locked_csv", height=150)
provider_json = st.text_area(t("provider_json"), value="", key="local_sim_provider_json", height=150)
confirmation_json = st.text_area(t("confirmation_json"), value="", key="local_sim_confirmation_json", height=110)
value_json = st.text_area(t("value_json"), value="", key="local_sim_value_json", height=110)
shadow_csv = st.text_area(t("shadow_csv"), value="", key="local_sim_shadow_csv", height=90)
review_json = st.text_area(t("review_json"), value="", key="local_sim_review_json", height=90)

if st.button(t("run"), key="local_sim_run"):
    st.session_state[REPORT_KEY] = build_local_update_simulation_from_text(
        workspace_id,
        locked_csv,
        provider_json,
        confirmation_json,
        value_json,
        shadow_csv,
        review_json,
        match_threshold=float(match_threshold),
        review_threshold=float(review_threshold),
        verified_confidence=float(verified_confidence),
        intake_review_confidence=float(intake_review_confidence),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

status = safe_text(report.get("status"))
status_key = "ready" if status == "SIMULATION READY" else "empty" if status == "NO ROWS" else "review"
st.write({t(status_key): True, t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})

metrics = st.columns(8)
metrics[0].metric("status", status)
metrics[1].metric("locked", report.get("locked_row_count", 0))
metrics[2].metric("provider", report.get("provider_event_count", 0))
metrics[3].metric("matched", report.get("matched_count", 0))
metrics[4].metric("changed", report.get("package_changed_count", 0))
metrics[5].metric("verified", report.get("verified_lane_count", 0))
metrics[6].metric("shadow", report.get("shadow_lane_count", 0))
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
    "matched_count": report.get("matched_count"),
    "package_changed_count": report.get("package_changed_count"),
    "verified_lane_count": report.get("verified_lane_count"),
    "review_lane_count": report.get("review_lane_count"),
    "shadow_lane_count": report.get("shadow_lane_count"),
    "quarantine_lane_count": report.get("quarantine_lane_count"),
    "official_metrics_row_count": report.get("official_metrics_row_count"),
    "shadow_learning_row_count": report.get("shadow_learning_row_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('stages')}")
st.dataframe(pd.DataFrame(report.get("stage_summary") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('downloads')}")
suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('simulation_hash'))}"
st.download_button(t("manifest"), export_simulation_manifest_json(report).encode("utf-8"), file_name=f"aba_local_simulation_manifest_{suffix}.json", mime="application/json", key=f"local_sim_manifest_{safe_text(report.get('simulation_hash'))}")
for name, body in dict(report.get("downloads") or {}).items():
    extension = "json" if name.endswith("json") else "csv"
    mime = "application/json" if extension == "json" else "text/csv"
    st.download_button(
        f"{t('download')}: {name}",
        safe_text(body).encode("utf-8"),
        file_name=f"aba_local_simulation_{name}_{suffix}.{extension}",
        mime=mime,
        key=f"local_sim_{safe_text(name)}_{safe_text(report.get('simulation_hash'))}",
    )

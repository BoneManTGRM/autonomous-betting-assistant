from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.event_match_resolver import (
    build_event_match_report_from_text,
    export_event_match_report_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Event Match Resolver", layout="wide")
LANG = render_app_sidebar("event_match_resolver", language_key="event_match_resolver_language")

REPORT_KEY = "event_match_resolver_report"

TEXT = {
    "en": {
        "title": "Event Match Resolver",
        "caption": "Preview-only matching between locked rows and provider events before any verified update flow.",
        "workspace_id": "Workspace ID",
        "locked_csv": "Locked proof rows CSV",
        "provider_json": "Provider events JSON",
        "match_threshold": "Match threshold",
        "review_threshold": "Review threshold",
        "run": "Run match resolver",
        "matched": "MATCHED",
        "low": "LOW CONFIDENCE",
        "none": "NO MATCH",
        "duplicate": "DUPLICATE MATCH",
        "manual": "MANUAL REVIEW",
        "preview_only": "PREVIEW ONLY",
        "proof_safe": "NO PROOF ROWS CHANGED",
        "summary": "Match summary",
        "rows": "Match rows",
        "candidates": "Top candidates",
        "download": "Download match report JSON",
        "no_report": "Run match resolver to view match details.",
    },
    "es": {
        "title": "Resolutor de Match de Eventos",
        "caption": "Vista previa para emparejar filas bloqueadas con eventos de proveedor antes de cualquier flujo verificado.",
        "workspace_id": "ID de workspace",
        "locked_csv": "CSV de filas proof bloqueadas",
        "provider_json": "JSON de eventos del proveedor",
        "match_threshold": "Umbral de match",
        "review_threshold": "Umbral de revision",
        "run": "Ejecutar resolutor de match",
        "matched": "MATCHED",
        "low": "LOW CONFIDENCE",
        "none": "NO MATCH",
        "duplicate": "DUPLICATE MATCH",
        "manual": "MANUAL REVIEW",
        "preview_only": "PREVIEW ONLY",
        "proof_safe": "NO PROOF ROWS CHANGED",
        "summary": "Resumen de match",
        "rows": "Filas de match",
        "candidates": "Candidatos principales",
        "download": "Descargar JSON de match",
        "no_report": "Ejecuta el resolutor para ver detalles.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "match"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="event_match_workspace_id"))

cols = st.columns(2)
match_threshold = cols[0].number_input(t("match_threshold"), min_value=0.50, max_value=1.0, value=0.82, step=0.01, key="event_match_threshold")
review_threshold = cols[1].number_input(t("review_threshold"), min_value=0.30, max_value=0.95, value=0.68, step=0.01, key="event_review_threshold")

locked_csv = st.text_area(t("locked_csv"), value="", key="event_match_locked_csv", height=180)
provider_json = st.text_area(t("provider_json"), value="", key="event_match_provider_json", height=180)

if st.button(t("run"), key="event_match_run"):
    st.session_state[REPORT_KEY] = build_event_match_report_from_text(
        workspace_id,
        locked_csv,
        provider_json,
        match_threshold=float(match_threshold),
        review_threshold=float(review_threshold),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

status = safe_text(report.get("status"))
status_key = "matched" if status == "MATCHED" else "manual" if status == "MANUAL REVIEW" else "none"
st.write({t(status_key): True, t("preview_only"): bool(report.get("preview_only")), t("proof_safe"): int(report.get("proof_rows_changed") or 0) == 0})

metrics = st.columns(7)
metrics[0].metric("status", status)
metrics[1].metric("locked", report.get("locked_row_count", 0))
metrics[2].metric("provider", report.get("provider_event_count", 0))
metrics[3].metric("matched", report.get("matched_count", 0))
metrics[4].metric("low", report.get("low_confidence_count", 0))
metrics[5].metric("duplicate", report.get("duplicate_match_count", 0))
metrics[6].metric("review", report.get("manual_review_count", 0))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "status": report.get("status"),
    "locked_row_count": report.get("locked_row_count"),
    "provider_event_count": report.get("provider_event_count"),
    "matched_count": report.get("matched_count"),
    "low_confidence_count": report.get("low_confidence_count"),
    "no_match_count": report.get("no_match_count"),
    "duplicate_match_count": report.get("duplicate_match_count"),
    "manual_review_count": report.get("manual_review_count"),
    "match_threshold": report.get("match_threshold"),
    "review_threshold": report.get("review_threshold"),
    "preview_only": report.get("preview_only"),
    "proof_rows_changed": report.get("proof_rows_changed"),
})

rows = list(report.get("match_rows") or [])
st.markdown(f"### {t('rows')}")
flat_rows = [{key: value for key, value in row.items() if key != "top_candidates"} for row in rows]
st.dataframe(pd.DataFrame(flat_rows), use_container_width=True, hide_index=True)

st.markdown(f"### {t('candidates')}")
candidate_rows = []
for row in rows:
    for item in row.get("top_candidates") or []:
        candidate_rows.append({"locked_row_id": row.get("locked_row_id"), **item})
st.dataframe(pd.DataFrame(candidate_rows), use_container_width=True, hide_index=True)

st.download_button(
    t("download"),
    export_event_match_report_json(report).encode("utf-8"),
    file_name=f"aba_event_match_{safe_text(report.get('workspace_id'))}_{_fragment(report.get('status'))}.json",
    mime="application/json",
    key=f"event_match_json_{safe_text(report.get('status'))}",
)

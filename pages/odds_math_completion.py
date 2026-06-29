from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.odds_math_completion import (
    build_odds_math_completion_report_from_text,
    export_odds_math_json,
    export_odds_rows_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Odds Math Completion", layout="wide")
LANG = render_app_sidebar("odds_math_completion", language_key="odds_math_completion_language")

REPORT_KEY = "odds_math_completion_report"

TEXT = {
    "en": {
        "title": "Odds Math Completion",
        "caption": "Validate odds math, fair price, minimum playable odds, EV, edge, no-vig market probability, and fractional Kelly without changing proof data.",
        "workspace_id": "Workspace ID",
        "odds_csv": "Odds rows CSV",
        "market_csv": "Optional full market sides CSV",
        "ev_buffer": "EV buffer",
        "safety_margin": "Safety margin",
        "kelly_fraction": "Kelly fraction",
        "max_stake": "Max stake fraction",
        "run": "Run odds math",
        "summary": "Odds summary",
        "rows": "Odds rows",
        "market": "No-vig market report",
        "download_json": "Download odds math JSON",
        "download_csv": "Download odds rows CSV",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run odds math to view outputs.",
    },
    "es": {
        "title": "Odds Math Completion",
        "caption": "Valida odds math, precio justo, odds mínimas jugables, EV, edge, probabilidad no-vig y Kelly fraccional sin cambiar proof data.",
        "workspace_id": "ID de workspace",
        "odds_csv": "CSV de odds rows",
        "market_csv": "CSV opcional de todos los lados del mercado",
        "ev_buffer": "Buffer EV",
        "safety_margin": "Margen de seguridad",
        "kelly_fraction": "Fracción Kelly",
        "max_stake": "Fracción máxima de stake",
        "run": "Ejecutar odds math",
        "summary": "Resumen odds",
        "rows": "Filas odds",
        "market": "Reporte no-vig del mercado",
        "download_json": "Descargar JSON odds math",
        "download_csv": "Descargar CSV odds rows",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta odds math para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "odds"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="odds_math_workspace_id"))

cols = st.columns(4)
ev_buffer = cols[0].number_input(t("ev_buffer"), min_value=-0.20, max_value=0.50, value=0.00, step=0.01, key="odds_math_ev_buffer")
safety_margin = cols[1].number_input(t("safety_margin"), min_value=0.00, max_value=1.00, value=0.02, step=0.01, key="odds_math_safety_margin")
kelly_fraction = cols[2].number_input(t("kelly_fraction"), min_value=0.00, max_value=1.00, value=0.25, step=0.05, key="odds_math_kelly_fraction")
max_stake = cols[3].number_input(t("max_stake"), min_value=0.00, max_value=0.25, value=0.03, step=0.01, key="odds_math_max_stake")

odds_csv = st.text_area(t("odds_csv"), value="", key="odds_math_odds_csv", height=180)
market_csv = st.text_area(t("market_csv"), value="", key="odds_math_market_csv", height=140)

if st.button(t("run"), key="odds_math_run"):
    st.session_state[REPORT_KEY] = build_odds_math_completion_report_from_text(
        workspace_id,
        odds_csv,
        market_csv,
        ev_buffer=float(ev_buffer),
        safety_margin=float(safety_margin),
        kelly_fraction=float(kelly_fraction),
        max_stake_fraction=float(max_stake),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(7)
metrics[0].metric("rows", report.get("row_count", 0))
metrics[1].metric("green", report.get("green_count", 0))
metrics[2].metric("yellow", report.get("yellow_count", 0))
metrics[3].metric("red", report.get("red_count", 0))
metrics[4].metric("warnings", report.get("data_warning_count", 0))
metrics[5].metric("playable", report.get("playable_count", 0))
metrics[6].metric("hash", _fragment(report.get("odds_math_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "odds_math_id": report.get("odds_math_id"),
    "odds_math_hash": report.get("odds_math_hash"),
    "row_count": report.get("row_count"),
    "playable_count": report.get("playable_count"),
    "blocked_count": report.get("blocked_count"),
    "ev_buffer": report.get("ev_buffer"),
    "safety_margin": report.get("safety_margin"),
    "kelly_fraction": report.get("kelly_fraction"),
    "max_stake_fraction": report.get("max_stake_fraction"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('market')}")
st.json(report.get("market_no_vig") or {})

st.markdown(f"### {t('rows')}")
st.dataframe(pd.DataFrame(report.get("odds_rows") or []), use_container_width=True, hide_index=True)

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('odds_math_hash'))}"
st.download_button(t("download_json"), export_odds_math_json(report).encode("utf-8"), file_name=f"aba_odds_math_{suffix}.json", mime="application/json", key=f"odds_math_json_{safe_text(report.get('odds_math_hash'))}")
st.download_button(t("download_csv"), export_odds_rows_csv(report).encode("utf-8"), file_name=f"aba_odds_math_rows_{suffix}.csv", mime="text/csv", key=f"odds_math_csv_{safe_text(report.get('odds_math_hash'))}")

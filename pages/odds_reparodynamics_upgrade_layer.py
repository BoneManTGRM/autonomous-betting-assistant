from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.odds_reparodynamics_upgrade_layer import (
    build_phase3e38_upgrade_report_from_text,
    export_drift_csv,
    export_market_groups_csv,
    export_phase3e38_json,
    export_repair_candidates_csv,
    export_upgraded_odds_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Odds + Reparodynamics Upgrade", layout="wide")
LANG = render_app_sidebar("odds_reparodynamics_upgrade_layer", language_key="odds_reparodynamics_upgrade_language")

REPORT_KEY = "odds_reparodynamics_upgrade_report"

TEXT = {
    "en": {
        "title": "Odds + Reparodynamics Upgrade Layer",
        "caption": "Grouped no-vig, best-book, CLV, minimum playable odds, segment drift, confidence intervals, and shadow repair candidates.",
        "workspace_id": "Workspace ID",
        "odds_csv": "Current odds CSV",
        "history_csv": "Historical graded rows CSV",
        "ev_buffer": "EV buffer",
        "safety_margin": "Safety margin",
        "max_age": "Max line age minutes",
        "min_segment": "Min segment rows",
        "drift_threshold": "Drift threshold",
        "run": "Run upgrade layer",
        "summary": "Upgrade summary",
        "odds_rows": "Upgraded odds rows",
        "market_groups": "Market groups",
        "best_books": "Best-book rows",
        "drift": "Segment drift",
        "repairs": "Repair candidates",
        "shadow": "Shadow scoring",
        "safety": "Safety gates",
        "download_json": "Download upgrade JSON",
        "download_odds": "Download upgraded odds CSV",
        "download_groups": "Download market groups CSV",
        "download_drift": "Download drift CSV",
        "download_repairs": "Download repair candidates CSV",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run the upgrade layer to view outputs.",
    },
    "es": {
        "title": "Odds + Reparodynamics Upgrade Layer",
        "caption": "No-vig agrupado, best-book, CLV, odds mínimas jugables, drift por segmento, intervalos y repair candidates shadow.",
        "workspace_id": "ID de workspace",
        "odds_csv": "CSV de odds actuales",
        "history_csv": "CSV de filas históricas calificadas",
        "ev_buffer": "Buffer EV",
        "safety_margin": "Margen de seguridad",
        "max_age": "Edad máxima de línea en minutos",
        "min_segment": "Mínimo de filas por segmento",
        "drift_threshold": "Umbral drift",
        "run": "Ejecutar upgrade layer",
        "summary": "Resumen upgrade",
        "odds_rows": "Filas odds mejoradas",
        "market_groups": "Grupos de mercado",
        "best_books": "Filas best-book",
        "drift": "Drift por segmento",
        "repairs": "Repair candidates",
        "shadow": "Shadow scoring",
        "safety": "Safety gates",
        "download_json": "Descargar JSON upgrade",
        "download_odds": "Descargar CSV odds mejoradas",
        "download_groups": "Descargar CSV market groups",
        "download_drift": "Descargar CSV drift",
        "download_repairs": "Descargar CSV repair candidates",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta el upgrade layer para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "upgrade"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="phase3e38_workspace_id"))

cols = st.columns(5)
ev_buffer = cols[0].number_input(t("ev_buffer"), min_value=-0.20, max_value=0.50, value=0.00, step=0.01, key="phase3e38_ev_buffer")
safety_margin = cols[1].number_input(t("safety_margin"), min_value=0.00, max_value=1.00, value=0.02, step=0.01, key="phase3e38_safety_margin")
max_age = cols[2].number_input(t("max_age"), min_value=1, max_value=1440, value=180, step=15, key="phase3e38_max_age")
min_segment = cols[3].number_input(t("min_segment"), min_value=3, max_value=500, value=10, step=1, key="phase3e38_min_segment")
drift_threshold = cols[4].number_input(t("drift_threshold"), min_value=0.01, max_value=0.50, value=0.08, step=0.01, key="phase3e38_drift_threshold")

odds_csv = st.text_area(t("odds_csv"), value="", key="phase3e38_odds_csv", height=180)
history_csv = st.text_area(t("history_csv"), value="", key="phase3e38_history_csv", height=180)

if st.button(t("run"), key="phase3e38_run"):
    st.session_state[REPORT_KEY] = build_phase3e38_upgrade_report_from_text(
        workspace_id,
        odds_csv,
        history_csv,
        ev_buffer=float(ev_buffer),
        safety_margin=float(safety_margin),
        max_age_minutes=int(max_age),
        min_segment_rows=int(min_segment),
        drift_threshold=float(drift_threshold),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("odds", report.get("odds_row_count", 0))
metrics[1].metric("history", report.get("history_row_count", 0))
metrics[2].metric("playable", report.get("playable_count", 0))
metrics[3].metric("blocked", report.get("blocked_count", 0))
metrics[4].metric("groups", report.get("market_group_count", 0))
metrics[5].metric("drift", report.get("drift_count", 0))
metrics[6].metric("repairs", report.get("repair_candidate_count", 0))
metrics[7].metric("hash", _fragment(report.get("upgrade_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "upgrade_id": report.get("upgrade_id"),
    "upgrade_hash": report.get("upgrade_hash"),
    "mode": report.get("mode"),
    "odds_row_count": report.get("odds_row_count"),
    "history_row_count": report.get("history_row_count"),
    "playable_count": report.get("playable_count"),
    "blocked_count": report.get("blocked_count"),
    "market_group_count": report.get("market_group_count"),
    "best_book_count": report.get("best_book_count"),
    "drift_count": report.get("drift_count"),
    "repair_candidate_count": report.get("repair_candidate_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('odds_rows')}")
st.dataframe(pd.DataFrame(report.get("upgraded_odds_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('market_groups')}")
st.dataframe(pd.DataFrame(report.get("market_groups") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('best_books')}")
st.dataframe(pd.DataFrame(report.get("best_book_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('drift')}")
st.dataframe(pd.DataFrame((report.get("segment_drift") or {}).get("segments") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('repairs')}")
st.dataframe(pd.DataFrame(report.get("repair_candidates") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('shadow')}")
st.json({key: value for key, value in (report.get("shadow_scoring") or {}).items() if key not in {"scored_candidates"}})

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('upgrade_hash'))}"
st.download_button(t("download_json"), export_phase3e38_json(report).encode("utf-8"), file_name=f"aba_phase3e38_upgrade_{suffix}.json", mime="application/json", key=f"phase3e38_json_{safe_text(report.get('upgrade_hash'))}")
st.download_button(t("download_odds"), export_upgraded_odds_csv(report).encode("utf-8"), file_name=f"aba_phase3e38_odds_{suffix}.csv", mime="text/csv", key=f"phase3e38_odds_{safe_text(report.get('upgrade_hash'))}")
st.download_button(t("download_groups"), export_market_groups_csv(report).encode("utf-8"), file_name=f"aba_phase3e38_market_groups_{suffix}.csv", mime="text/csv", key=f"phase3e38_groups_{safe_text(report.get('upgrade_hash'))}")
st.download_button(t("download_drift"), export_drift_csv(report).encode("utf-8"), file_name=f"aba_phase3e38_drift_{suffix}.csv", mime="text/csv", key=f"phase3e38_drift_{safe_text(report.get('upgrade_hash'))}")
st.download_button(t("download_repairs"), export_repair_candidates_csv(report).encode("utf-8"), file_name=f"aba_phase3e38_repairs_{suffix}.csv", mime="text/csv", key=f"phase3e38_repairs_{safe_text(report.get('upgrade_hash'))}")

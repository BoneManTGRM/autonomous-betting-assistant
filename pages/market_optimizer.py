from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.market_optimizer_preview import (
    build_market_optimizer_preview_from_text,
    export_avoid_list_csv,
    export_best_books_csv,
    export_chain_builder_csv,
    export_marco_mode_json,
    export_market_hunter_csv,
    export_market_optimizer_json,
    export_market_optimizer_manifest_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Market Optimizer", layout="wide")
LANG = render_app_sidebar("market_optimizer", language_key="market_optimizer_language")

REPORT_KEY = "market_optimizer_preview_report"

TEXT = {
    "en": {
        "title": "Market Optimizer Preview",
        "caption": "Preview-only Market Hunter, Optimizer, Chain Builder, Avoid List, and Marco Mode output.",
        "workspace_id": "Workspace ID",
        "bankroll": "Preview bankroll units",
        "market_csv": "Market / sportsbook rows CSV",
        "history_csv": "Optional proof/history rows CSV",
        "run": "Run market optimizer preview",
        "summary": "Optimizer summary",
        "hunter": "Market Hunter rows",
        "books": "Best-book comparison",
        "chains": "Chain Builder preview",
        "avoid": "Avoid list",
        "marco": "Marco Mode / Pro View",
        "safety": "Safety gates",
        "download_json": "Download optimizer JSON",
        "download_hunter": "Download Market Hunter CSV",
        "download_books": "Download best-books CSV",
        "download_chains": "Download Chain Builder CSV",
        "download_avoid": "Download Avoid List CSV",
        "download_marco": "Download Marco Mode JSON",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run the market optimizer preview to view outputs.",
    },
    "es": {
        "title": "Market Optimizer Preview",
        "caption": "Preview-only Market Hunter, Optimizer, Chain Builder, Avoid List y Marco Mode.",
        "workspace_id": "ID de workspace",
        "bankroll": "Bankroll preview units",
        "market_csv": "CSV market / sportsbook rows",
        "history_csv": "CSV proof/history opcional",
        "run": "Ejecutar market optimizer preview",
        "summary": "Resumen optimizer",
        "hunter": "Market Hunter rows",
        "books": "Comparación best-book",
        "chains": "Chain Builder preview",
        "avoid": "Avoid list",
        "marco": "Marco Mode / Pro View",
        "safety": "Safety gates",
        "download_json": "Descargar JSON optimizer",
        "download_hunter": "Descargar CSV Market Hunter",
        "download_books": "Descargar CSV best-books",
        "download_chains": "Descargar CSV Chain Builder",
        "download_avoid": "Descargar CSV Avoid List",
        "download_marco": "Descargar JSON Marco Mode",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta el market optimizer preview para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "optimizer"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="market_optimizer_workspace_id"))
bankroll = st.number_input(t("bankroll"), min_value=1.0, value=1000.0, step=50.0, key="market_optimizer_bankroll")
market_csv = st.text_area(t("market_csv"), value="", key="market_optimizer_market_csv", height=220)
history_csv = st.text_area(t("history_csv"), value="", key="market_optimizer_history_csv", height=160)

if st.button(t("run"), key="market_optimizer_run"):
    st.session_state[REPORT_KEY] = build_market_optimizer_preview_from_text(workspace_id, market_csv, history_csv, bankroll)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("markets", report.get("market_row_count", 0))
metrics[1].metric("playable", report.get("playable_count", 0))
metrics[2].metric("watch", report.get("watch_count", 0))
metrics[3].metric("wait", report.get("wait_count", 0))
metrics[4].metric("no bet", report.get("no_play_count", 0))
metrics[5].metric("low", report.get("low_risk_count", 0))
metrics[6].metric("high", report.get("high_risk_count", 0))
metrics[7].metric("hash", _fragment(report.get("optimizer_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "optimizer_id": report.get("optimizer_id"),
    "optimizer_hash": report.get("optimizer_hash"),
    "mode": report.get("mode"),
    "market_row_count": report.get("market_row_count"),
    "history_row_count": report.get("history_row_count"),
    "playable_count": report.get("playable_count"),
    "watch_count": report.get("watch_count"),
    "wait_count": report.get("wait_count"),
    "no_play_count": report.get("no_play_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('hunter')}")
st.dataframe(pd.DataFrame(report.get("market_hunter_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('books')}")
st.dataframe(pd.DataFrame(report.get("best_book_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('chains')}")
st.dataframe(pd.DataFrame(report.get("chain_builder_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('avoid')}")
st.dataframe(pd.DataFrame(report.get("avoid_list") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('marco')}")
st.json(report.get("marco_mode") or {})

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('optimizer_hash'))}"
st.download_button(t("download_json"), export_market_optimizer_json(report).encode("utf-8"), file_name=f"aba_market_optimizer_{suffix}.json", mime="application/json", key=f"market_optimizer_json_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_hunter"), export_market_hunter_csv(report).encode("utf-8"), file_name=f"aba_market_hunter_{suffix}.csv", mime="text/csv", key=f"market_hunter_csv_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_books"), export_best_books_csv(report).encode("utf-8"), file_name=f"aba_best_books_{suffix}.csv", mime="text/csv", key=f"market_books_csv_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_chains"), export_chain_builder_csv(report).encode("utf-8"), file_name=f"aba_chain_builder_{suffix}.csv", mime="text/csv", key=f"market_chains_csv_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_avoid"), export_avoid_list_csv(report).encode("utf-8"), file_name=f"aba_avoid_list_{suffix}.csv", mime="text/csv", key=f"market_avoid_csv_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_marco"), export_marco_mode_json(report).encode("utf-8"), file_name=f"aba_marco_mode_{suffix}.json", mime="application/json", key=f"market_marco_json_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_manifest"), export_market_optimizer_manifest_json(report).encode("utf-8"), file_name=f"aba_market_optimizer_manifest_{suffix}.json", mime="application/json", key=f"market_manifest_json_{safe_text(report.get('optimizer_hash'))}")

from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.subscriber_ledger import (
    build_subscriber_ledger_reports_from_text,
    export_ledger_checks_csv,
    export_ledger_manifest_json,
    export_ledger_rows_csv,
    export_market_type_performance_csv,
    export_mistake_patterns_csv,
    export_sport_performance_csv,
    export_sportsbook_performance_csv,
    export_subscriber_ledger_json,
    export_subscriber_summaries_csv,
)

st.set_page_config(page_title="Subscriber Ledger", layout="wide")
LANG = render_app_sidebar("subscriber_ledger", language_key="subscriber_ledger_language")

REPORT_KEY = "subscriber_ledger_report"

TEXT = {
    "en": {
        "title": "Subscriber Ledger",
        "caption": "Track subscriber-specific results, ROI, win rate, unique events, sportsbook performance, and mistake patterns.",
        "workspace_id": "Workspace ID",
        "ledger_csv": "Subscriber ledger CSV",
        "run": "Build ledger reports",
        "summary": "Ledger summary",
        "global": "Global summary",
        "subs": "Subscriber summaries",
        "rows": "Normalized ledger rows",
        "sports": "Sport performance",
        "markets": "Market-type performance",
        "books": "Sportsbook performance",
        "patterns": "Mistake patterns",
        "checks": "Checks",
        "safety": "Safety gates",
        "download_json": "Download ledger JSON",
        "download_rows": "Download ledger rows CSV",
        "download_subs": "Download subscriber summaries CSV",
        "download_sports": "Download sport performance CSV",
        "download_markets": "Download market-type performance CSV",
        "download_books": "Download sportsbook performance CSV",
        "download_patterns": "Download mistake patterns CSV",
        "download_checks": "Download checks CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Build ledger reports to view outputs.",
    },
    "es": {
        "title": "Subscriber Ledger",
        "caption": "Rastrea resultados por subscriber, ROI, win rate, eventos únicos, sportsbook performance y mistake patterns.",
        "workspace_id": "ID de workspace",
        "ledger_csv": "CSV subscriber ledger",
        "run": "Construir ledger reports",
        "summary": "Resumen ledger",
        "global": "Resumen global",
        "subs": "Resumen por subscriber",
        "rows": "Filas ledger normalizadas",
        "sports": "Performance por deporte",
        "markets": "Performance por market type",
        "books": "Performance por sportsbook",
        "patterns": "Mistake patterns",
        "checks": "Checks",
        "safety": "Safety gates",
        "download_json": "Descargar JSON ledger",
        "download_rows": "Descargar CSV ledger rows",
        "download_subs": "Descargar CSV subscriber summaries",
        "download_sports": "Descargar CSV sport performance",
        "download_markets": "Descargar CSV market-type performance",
        "download_books": "Descargar CSV sportsbook performance",
        "download_patterns": "Descargar CSV mistake patterns",
        "download_checks": "Descargar CSV checks",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Construye ledger reports para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "ledger"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="subscriber_ledger_workspace_id"))
ledger_csv = st.text_area(t("ledger_csv"), value="", key="subscriber_ledger_csv", height=240)

if st.button(t("run"), key="subscriber_ledger_run"):
    st.session_state[REPORT_KEY] = build_subscriber_ledger_reports_from_text(workspace_id, ledger_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("ledger_status", ""))
metrics[1].metric("rows", report.get("ledger_row_count", 0))
metrics[2].metric("subscribers", report.get("subscriber_count", 0))
metrics[3].metric("unique events", report.get("unique_event_count", 0))
metrics[4].metric("ROI", report.get("global_summary", {}).get("roi"))
metrics[5].metric("win rate", report.get("global_summary", {}).get("win_rate_ex_push_cancel"))
metrics[6].metric("fail", report.get("fail_count", 0))
metrics[7].metric("hash", _fragment(report.get("ledger_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "ledger_run_id": report.get("ledger_run_id"),
    "ledger_hash": report.get("ledger_hash"),
    "mode": report.get("mode"),
    "ledger_status": report.get("ledger_status"),
    "ledger_row_count": report.get("ledger_row_count"),
    "subscriber_count": report.get("subscriber_count"),
    "unique_event_count": report.get("unique_event_count"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('global')}")
st.json(report.get("global_summary") or {})

st.markdown(f"### {t('subs')}")
st.dataframe(pd.DataFrame(report.get("subscriber_summaries") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('rows')}")
st.dataframe(pd.DataFrame(report.get("ledger_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('sports')}")
st.dataframe(pd.DataFrame(report.get("sport_performance") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('markets')}")
st.dataframe(pd.DataFrame(report.get("market_type_performance") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('books')}")
st.dataframe(pd.DataFrame(report.get("sportsbook_performance") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('patterns')}")
st.dataframe(pd.DataFrame(report.get("mistake_patterns") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("ledger_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('ledger_hash'))}"
st.download_button(t("download_json"), export_subscriber_ledger_json(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_{suffix}.json", mime="application/json", key=f"subscriber_ledger_json_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_rows"), export_ledger_rows_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_rows_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_rows_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_subs"), export_subscriber_summaries_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_summaries_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_subs_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_sports"), export_sport_performance_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_sports_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_sports_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_markets"), export_market_type_performance_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_markets_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_markets_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_books"), export_sportsbook_performance_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_books_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_books_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_patterns"), export_mistake_patterns_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_patterns_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_patterns_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_checks"), export_ledger_checks_csv(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_checks_{suffix}.csv", mime="text/csv", key=f"subscriber_ledger_checks_{safe_text(report.get('ledger_hash'))}")
st.download_button(t("download_manifest"), export_ledger_manifest_json(report).encode("utf-8"), file_name=f"aba_subscriber_ledger_manifest_{suffix}.json", mime="application/json", key=f"subscriber_ledger_manifest_{safe_text(report.get('ledger_hash'))}")

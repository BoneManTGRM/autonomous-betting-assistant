from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_repair_runner import (
    column_mapping_preview,
    list_recent_simulation_runs,
    rows_from_csv_bytes,
    run_adaptive_repair_scan,
    runner_report_to_markdown,
    save_runner_report,
)
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import tr, upload_helper

st.set_page_config(page_title="Adaptive Repair Simulation", layout="wide")
LANG = render_app_sidebar("adaptive_repair_simulation", language_key="adaptive_repair_simulation_language")
require_streamlit_access(st, allow_roles={"admin"})

st.title(tr(LANG, "ABA Adaptive Repair Runner", "Motor de Reparación Adaptativa ABA"))
st.caption(tr(
    LANG,
    "Internal runner control panel. Phase 3A observes and reports only; it does not change live picks.",
    "Panel de control del motor interno. Fase 3A solo observa e informa; no cambia picks en vivo.",
))

SAFETY_COLUMNS = st.columns(3)
SAFETY_COLUMNS[0].metric("Repair Mode", "OFF")
SAFETY_COLUMNS[1].metric("Shadow Mode", "OFF")
SAFETY_COLUMNS[2].metric("Live Pick Changes", "OFF")
st.info("Learning Impact: Simulation only | TGRM Activation: OFF | Hidden Value Activation: OFF | Confidence Calibration Activation: OFF | Bet Tier Changes: OFF | Production Model Mutation: OFF")

st.subheader("Run Adaptive Repair Runner")
include_system = st.checkbox("Include available local system sources", value=True)
upload = st.file_uploader("Optional graded CSV for manual simulation", type=["csv"], help=upload_helper(LANG))

uploaded_rows = None
uploaded_bytes = None
uploaded_name = "uploaded_rows.csv"
if upload is not None:
    uploaded_bytes = upload.getvalue()
    uploaded_name = upload.name
    try:
        uploaded_rows = rows_from_csv_bytes(uploaded_bytes)
        st.success(f"Loaded {len(uploaded_rows)} uploaded row(s) for simulation preview.")
        preview = pd.DataFrame(uploaded_rows)
        st.dataframe(preview.head(50), use_container_width=True)
        st.subheader("CSV column-mapping preview")
        mapping = column_mapping_preview(uploaded_rows)
        st.json(mapping)
        for limitation in mapping.get("limitations", []):
            st.warning(limitation)
    except Exception as exc:
        st.error(f"Could not parse uploaded CSV: {exc}")
        uploaded_rows = None

if st.button("Run system-wide Adaptive Repair scan"):
    report = run_adaptive_repair_scan(
        uploaded_rows=uploaded_rows,
        uploaded_filename=uploaded_name,
        uploaded_bytes=uploaded_bytes,
        include_system_sources=include_system,
    )
    markdown = runner_report_to_markdown(report)
    json_report = report.to_json()

    st.subheader("Runner safety state")
    st.json(report.safety_state)

    st.subheader("Source availability")
    st.dataframe(pd.DataFrame(report.sources), use_container_width=True)

    source_errors = [source for source in report.sources if source.get("error")]
    if source_errors:
        st.warning("Some sources failed to load. The runner continued safely.")
        st.dataframe(pd.DataFrame(source_errors), use_container_width=True)

    base = report.diagnostics.get("base_report", {})
    row = base.get("row_level", {})
    event = base.get("unique_event_level", {})
    diag = report.diagnostics
    quality = diag.get("data_quality", {})

    st.subheader("Core metrics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total rows", base.get("total_rows", 0))
    c2.metric("Completed W/L rows", row.get("completed", 0))
    c3.metric("Row record", f"{row.get('wins', 0)}-{row.get('losses', 0)}")
    c4.metric("Row win rate", row.get("win_rate_display", "n/a"))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Unique events", event.get("unique_events", 0))
    c6.metric("Unique-event win rate", event.get("win_rate_display", "n/a"))
    c7.metric("Mixed unique events", event.get("mixed_events", 0))
    c8.metric("Exact duplicate rows", diag.get("duplicate_rows", 0))

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Pushes", row.get("pushes", 0))
    c10.metric("Voids", row.get("voids", 0))
    c11.metric("Cancels", row.get("cancels", 0))
    c12.metric("Unknown", row.get("unknown", 0))

    st.subheader("Data quality")
    st.metric("Data-quality score", quality.get("score", "n/a"))
    if quality.get("penalties"):
        st.warning("Data-quality penalties detected.")
        st.write(quality.get("penalties"))
    else:
        st.success("No data-quality penalties detected.")

    st.subheader("Column coverage")
    st.dataframe(pd.DataFrame.from_dict(diag.get("column_coverage", {}), orient="index"), use_container_width=True)
    for item in report.unavailable_data:
        st.warning(item)

    st.subheader("Same-event review examples")
    groups = diag.get("same_event_groups", [])
    if groups:
        st.dataframe(pd.DataFrame(groups), use_container_width=True)
    else:
        st.info("No same-event review examples detected.")

    st.subheader("Watchlist-only pattern candidates")
    if report.pattern_candidates:
        st.dataframe(pd.DataFrame(report.pattern_candidates), use_container_width=True)
    else:
        st.info("No watchlist pattern candidates detected.")

    st.subheader("RYE / Shadow Mode readiness")
    st.json(report.readiness)

    saved = save_runner_report(report)
    st.success(f"Simulation run saved: {saved['run_dir']}")

    st.download_button("Download Markdown report", markdown.encode("utf-8"), file_name=f"adaptive_repair_{report.run_id}.md", mime="text/markdown")
    st.download_button("Download JSON report", json_report.encode("utf-8"), file_name=f"adaptive_repair_{report.run_id}.json", mime="application/json")

st.subheader("Recent saved simulation runs")
recent = list_recent_simulation_runs()
if recent:
    st.dataframe(pd.DataFrame(recent), use_container_width=True)
else:
    st.info("No saved simulation runs found yet.")

st.warning("Phase 3A is simulation-only. No live repairs, confidence changes, filters, bet-tier changes, bankroll changes, sportsbook recommendations, or production model mutations are active.")

from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.grading_rules import summarize_event_level, summarize_row_level
from autonomous_betting_agent.ledger_types import LEDGER_TYPES
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage

st.set_page_config(page_title="Local First Admin", layout="wide")
render_app_sidebar("local_first_admin", language_key="local_first_admin_language")

st.title("Local First Admin")
st.caption("Local SQLite/CSV proof storage, ledger counts, audit log, and export controls. No cloud server required.")

store = LocalStorage()
if store.using_sqlite:
    st.success("Using local SQLite storage: data/aba_signal_pro.sqlite")
else:
    st.warning("SQLite is unavailable. The app is using CSV fallback storage in data/ledgers.")
    if store.sqlite_error:
        st.caption(store.sqlite_error)

rows = store.load_rows()
ledger_counts = {ledger: len(store.load_rows(ledger)) for ledger in sorted(LEDGER_TYPES)}

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total local rows", len(rows))
col2.metric("Official rows", ledger_counts.get("official", 0))
col3.metric("Research rows", ledger_counts.get("research", 0))
col4.metric("Quarantine rows", ledger_counts.get("quarantine", 0))

st.subheader("Ledger counts")
st.dataframe(pd.DataFrame([{"ledger_type": key, "rows": value} for key, value in ledger_counts.items()]), use_container_width=True)

st.subheader("Record summaries")
row_summary = summarize_row_level(rows)
event_summary = summarize_event_level(rows)
left, right = st.columns(2)
with left:
    st.markdown("**Row-level summary**")
    st.dataframe(pd.DataFrame([row_summary]), use_container_width=True)
with right:
    st.markdown("**Event-level summary**")
    st.dataframe(pd.DataFrame([event_summary]), use_container_width=True)

st.subheader("Rows")
ledger_filter = st.selectbox("Ledger", ["all"] + sorted(LEDGER_TYPES))
visible_rows = rows if ledger_filter == "all" else store.load_rows(ledger_filter)
if visible_rows:
    st.dataframe(pd.DataFrame(visible_rows), use_container_width=True)
    export_df = pd.DataFrame(visible_rows)
    st.download_button(
        "Download visible rows as CSV",
        export_df.to_csv(index=False).encode("utf-8"),
        file_name=f"aba_{ledger_filter}_rows.csv",
        mime="text/csv",
    )
else:
    st.info("No local rows found yet. Save proof rows through the app or import existing CSV data through existing workflows.")

st.subheader("Audit log")
audit = store.load_audit_log(limit=250)
if audit:
    st.dataframe(pd.DataFrame(audit), use_container_width=True)
else:
    st.info("No local audit events found yet.")

st.warning("Analytics and proof tracking only. This page does not guarantee outcomes or returns.")

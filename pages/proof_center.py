from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.explanations import build_client_safe_pick_summary
from autonomous_betting_agent.grading_rules import summarize_event_level, summarize_row_level
from autonomous_betting_agent.ledger_types import classify_ledger_type, is_future_locked, public_metric_allowed
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage

st.set_page_config(page_title="Proof Center", layout="wide")
render_app_sidebar("proof_center", language_key="proof_center_language")
require_streamlit_access(st, allow_roles={"admin", "client", "demo"})

st.title("Proof Center")
st.caption("Unified proof review, proof ID verification, row-level/event-level records, and local proof rows.")
st.warning("Proof Center is for analytics and proof tracking only. It does not guarantee outcomes or returns.")

store = LocalStorage()
rows = store.load_rows()

row_summary = summarize_row_level(rows)
event_summary = summarize_event_level(rows)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Local rows", len(rows))
col2.metric("Row record", f"{row_summary['wins']}-{row_summary['losses']}")
col3.metric("Events", event_summary.get("events", 0))
col4.metric("Event record", f"{event_summary['wins']}-{event_summary['losses']}")

tabs = st.tabs(["Summary", "Proof ID Verification", "Proof Audit", "Row vs Event Record", "Local Proof Rows"])

with tabs[0]:
    st.subheader("Public proof summary")
    if not rows:
        st.info("No local proof rows found yet.")
    else:
        public_rows = [row for row in rows if public_metric_allowed(row)]
        st.metric("Public-safe rows", len(public_rows))
        st.metric("Research/review rows", max(0, len(rows) - len(public_rows)))
        st.dataframe(pd.DataFrame([{"scope": "row_level", **row_summary}, {"scope": "event_level", **event_summary}]), use_container_width=True)
    st.page_link("pages/public_proof_dashboard.py", label="Open legacy Public Proof Dashboard")
    st.page_link("pages/proof_control_center.py", label="Open legacy Proof Control Center")

with tabs[1]:
    st.subheader("Proof ID Verification")
    proof_id = st.text_input("Proof ID", "").strip()
    if not proof_id:
        st.info("Enter a proof ID to verify a local row.")
    else:
        matches = [row for row in rows if str(row.get("proof_id") or "").strip() == proof_id]
        if not matches:
            st.error("No local row found for that proof ID.")
        else:
            row = matches[0]
            ledger_type = classify_ledger_type(row)
            future_locked = is_future_locked(row)
            public_safe = public_metric_allowed(row)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Ledger type", ledger_type)
            c2.metric("Forward locked", "Yes" if future_locked else "No")
            c3.metric("Public-safe", "Yes" if public_safe else "No")
            c4.metric("Grade", str(row.get("grade") or row.get("result") or "pending"))
            st.write({
                "proof_id": row.get("proof_id"),
                "proof_hash": row.get("proof_hash"),
                "locked_at_utc": row.get("locked_at_utc"),
                "event_start_time": row.get("event_start_time") or row.get("commence_time"),
                "event_name": row.get("event_name") or row.get("event") or row.get("matchup"),
                "prediction": row.get("prediction") or row.get("pick") or row.get("selection"),
                "market": row.get("market") or row.get("market_type"),
                "odds_audit_status": row.get("odds_audit_status") or row.get("audit_status"),
            })
            st.info(build_client_safe_pick_summary(row))

with tabs[2]:
    st.subheader("Proof audit")
    if not rows:
        st.info("No rows available for audit.")
    else:
        audit_rows = []
        for row in rows:
            audit_rows.append({
                "proof_id": row.get("proof_id", ""),
                "ledger_type": classify_ledger_type(row),
                "forward_locked": is_future_locked(row),
                "public_safe": public_metric_allowed(row),
                "has_proof_hash": bool(row.get("proof_hash")),
                "grade": row.get("grade") or row.get("result") or "pending",
                "event": row.get("event_name") or row.get("event") or row.get("matchup"),
            })
        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True)

with tabs[3]:
    st.subheader("Row-level vs event-level record")
    left, right = st.columns(2)
    with left:
        st.markdown("**Row-level summary**")
        st.dataframe(pd.DataFrame([row_summary]), use_container_width=True)
    with right:
        st.markdown("**Event-level summary**")
        st.dataframe(pd.DataFrame([event_summary]), use_container_width=True)
    st.caption("Use event-level counts when multiple rows belong to the same matchup/game.")

with tabs[4]:
    st.subheader("Local proof rows")
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        st.download_button("Download local proof rows", df.to_csv(index=False).encode("utf-8"), file_name="local_proof_rows.csv", mime="text/csv")
    else:
        st.info("No local proof rows found yet.")

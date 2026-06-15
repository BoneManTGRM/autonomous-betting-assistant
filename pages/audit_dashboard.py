from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.audit import audit_dashboard_metrics, enrich_prediction_frame
from autonomous_betting_agent.mobile_report import ACTIONABLE_TIERS, compact_report_frame, rejection_summary, render_pick_cards

st.set_page_config(page_title="Prediction Audit Dashboard", layout="wide")
st.title("Prediction Audit Dashboard")
st.caption("Upload a Pro Predictor CSV to add odds fields, confidence tiers, clean grading labels, unit profit/loss, ROI, and dashboard metrics.")


def pct(value):
    if value is None or value == "":
        return ""
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return ""


def read_csv_input() -> pd.DataFrame:
    upload = st.file_uploader("Upload prediction CSV", type=["csv"], accept_multiple_files=False)
    pasted = st.text_area("Or paste CSV text", height=120)
    if upload is not None:
        return pd.read_csv(upload)
    if pasted.strip():
        return pd.read_csv(StringIO(pasted.strip()))
    return pd.DataFrame()


stake_units = st.number_input("Stake units per pick", min_value=0.01, max_value=1000.0, value=1.0, step=0.25)
frame = read_csv_input()

if frame.empty:
    st.info("Upload or paste a CSV to run the audit dashboard.")
    st.stop()

enriched = enrich_prediction_frame(frame, stake_units=float(stake_units))
metrics = audit_dashboard_metrics(enriched)
issues = rejection_summary(enriched)
actionable = enriched[enriched["confidence_tier"].isin(ACTIONABLE_TIERS)] if "confidence_tier" in enriched.columns else pd.DataFrame()
missing_odds = int(issues.loc[issues["Issue"] == "Missing odds / price", "Count"].sum()) if not issues.empty else 0

st.subheader("Audit summary")
cols = st.columns(8)
cols[0].metric("Rows", metrics["total_rows"])
cols[1].metric("Actionable", len(actionable))
cols[2].metric("Official graded", metrics["official_graded"])
cols[3].metric("Wins", metrics["wins"])
cols[4].metric("Losses", metrics["losses"])
cols[5].metric("Win rate", pct(metrics["win_rate"]))
cols[6].metric("Units", f"{metrics['units']:.2f}")
cols[7].metric("ROI", "" if metrics["roi_percent"] is None else f"{metrics['roi_percent']:.2f}%")

qcols = st.columns(4)
qcols[0].metric("A+ picks", metrics["a_plus_count"])
qcols[1].metric("Pending", metrics["pending"])
qcols[2].metric("Needs review", metrics["review_needed"])
qcols[3].metric("Missing odds", missing_odds)

if missing_odds:
    st.warning("Some rows are missing odds. Profit, ROI, EV, and break-even rate cannot be trusted for those rows until best_price or decimal_price is filled.")

st.subheader("Best picks first")
render_pick_cards(actionable)

with st.expander("Why rows were rejected or marked Watch Only", expanded=True):
    st.dataframe(issues, use_container_width=True, hide_index=True)

st.subheader("Confidence-tier performance")
tier_rows = []
for tier, group in enriched.groupby("confidence_tier", dropna=False):
    official = group[group["audit_inclusion"] == "official"]
    wins = int((official["result_status"] == "win").sum()) if not official.empty else 0
    losses = int((official["result_status"] == "loss").sum()) if not official.empty else 0
    graded = wins + losses
    units = float(official["profit_units"].dropna().sum()) if not official.empty else 0.0
    staked = float(official["stake_units"].dropna().sum()) if not official.empty else 0.0
    tier_rows.append({"confidence_tier": tier, "rows": len(group), "official_graded": graded, "wins": wins, "losses": losses, "win_rate": "" if graded == 0 else f"{wins / graded:.1%}", "units": round(units, 4), "roi_percent": "" if staked <= 0 else f"{units / staked:.1%}"})
st.dataframe(pd.DataFrame(tier_rows), use_container_width=True, hide_index=True)

with st.expander("Compact mobile table", expanded=True):
    st.dataframe(compact_report_frame(enriched), use_container_width=True, hide_index=True)

with st.expander("Full technical table", expanded=False):
    st.dataframe(enriched, use_container_width=True, hide_index=True)

st.download_button("Download audit-enriched CSV", enriched.to_csv(index=False), file_name="pro_predictor_audit_enriched.csv", mime="text/csv")

with st.expander("Clean grading rules", expanded=False):
    st.write({"graded_clean": "Confirmed final result and no mismatch/review flags.", "void": "Postponed, cancelled, abandoned, push, or no-action result.", "review_needed": "Wrong format, bad matchup, unconfirmed result, or manual-check flag.", "pending": "Live, future, unknown, or ungraded result."})

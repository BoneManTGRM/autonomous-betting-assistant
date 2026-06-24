from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.license_status import load_license_records, make_license_record, upsert_license_record
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Local License Admin", layout="wide")
render_app_sidebar("local_license_admin", language_key="local_license_admin_language")
require_streamlit_access(st, allow_roles={"admin"})

st.title("Local License Admin")
st.caption("Manual local license tracking only. No Stripe dependency and no payment processing.")

with st.form("license_form"):
    client_name = st.text_input("Client name")
    client_status = st.selectbox("Client status", ["trial", "active", "inactive", "expired"])
    subscription_tier = st.text_input("Subscription tier", "private_beta")
    manual_payment_status = st.text_input("Manual payment status", "manual")
    renewal_date = st.text_input("Renewal date", "")
    notes = st.text_area("Notes", "")
    future_stripe_ready = st.checkbox("Future Stripe-ready placeholder", value=False)
    submitted = st.form_submit_button("Save local license record")

if submitted:
    if not client_name.strip():
        st.error("Client name is required.")
    else:
        record = make_license_record(client_name, client_status, subscription_tier, manual_payment_status, renewal_date, notes, future_stripe_ready)
        upsert_license_record(record)
        st.success("Manual local license record saved.")

records = load_license_records()
if records:
    df = pd.DataFrame([asdict(record) for record in records])
    st.dataframe(df, use_container_width=True)
    st.download_button("Download local license CSV", df.to_csv(index=False).encode("utf-8"), file_name="local_license_status.csv", mime="text/csv")
else:
    st.info("No local license records found yet.")

st.warning("Manual license tracking only. This page does not process payments, connect to Stripe, or grant legal/financial guarantees.")

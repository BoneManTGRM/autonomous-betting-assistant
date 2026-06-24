from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.report_exports import render_html_report, render_markdown_report, render_messenger_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage

st.set_page_config(page_title="Report Studio Local Export", layout="wide")
render_app_sidebar("report_studio_local_export", language_key="report_studio_local_export_language")
require_streamlit_access(st, allow_roles={"admin", "client"})

st.title("Report Studio Local Export")
st.caption("Generate client-ready Markdown, HTML, and copy/paste report output from local proof rows. No cloud server required.")

store = LocalStorage()
rows = store.load_rows()

if not rows:
    st.info("No local rows found yet. Save or import proof rows first, then return here to export reports.")
    st.stop()

with st.sidebar:
    st.markdown("### Report settings")
    title = st.text_input("Report title", "ABA Signal Pro Report")
    client_name = st.text_input("Client name", "")
    public_safe = st.toggle("Public-safe mode", value=True, help="Only include rows eligible for public/client proof metrics.")
    background = st.text_input("Background image URL or local reference", "")

markdown_report = render_markdown_report(rows, title=title, client_name=client_name, public_safe=public_safe)
html_report = render_html_report(rows, title=title, client_name=client_name, background_image_url=background, public_safe=public_safe)
message_report = render_messenger_report(rows, title=title)

st.subheader("Copy/paste report")
st.text_area("WhatsApp / Telegram / email-ready summary", message_report, height=140)

st.subheader("Markdown report")
st.download_button(
    "Download Markdown report",
    markdown_report.encode("utf-8"),
    file_name="aba_signal_pro_report.md",
    mime="text/markdown",
)
st.text_area("Markdown preview", markdown_report, height=360)

st.subheader("HTML report")
st.download_button(
    "Download HTML report",
    html_report.encode("utf-8"),
    file_name="aba_signal_pro_report.html",
    mime="text/html",
)
with st.expander("HTML preview/source"):
    st.code(html_report, language="html")

st.warning("Report Studio is a presentation and proof-tracking tool only. It does not guarantee wins, returns, or outcomes.")

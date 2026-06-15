from __future__ import annotations

import streamlit as st

root_memory_upload = st.file_uploader(
    "Emergency ARA memory CSV upload",
    type=["csv"],
    accept_multiple_files=False,
    key="root_ara_memory_csv_upload_v1",
    help="Use this if the normal upload button lower on the page does not open. This fills the ARA memory paste fallback automatically.",
)
if root_memory_upload is not None:
    try:
        st.session_state["ara_memory_csv_paste"] = root_memory_upload.getvalue().decode("utf-8", errors="replace")
        st.success("ARA memory CSV loaded into the paste fallback below.")
    except Exception as exc:
        st.warning(f"Could not read emergency upload: {exc}")

import pages.pro_predictor  # noqa: F401,E402

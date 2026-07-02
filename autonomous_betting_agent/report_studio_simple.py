from __future__ import annotations

import importlib
import pandas as pd
import streamlit as st

import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_live_api_enrichment import enrich_rows_with_live_api_data, install as install_live
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch


def _safe(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value or "report"))


def render() -> None:
    st.set_page_config(page_title="Report Studio", layout="wide")
    st.title("Report Studio")
    st.caption("Compact magazine export mode is active.")
    module = apply_magazine_sale_ready_patch(install_live(importlib.reload(magazine_book_export)))
    upload = st.file_uploader("Upload CSV rows", type=["csv"])
    if upload is None:
        st.warning("Upload the newest CSV to generate the magazine while the full studio UI is restored.")
        return
    raw = pd.read_csv(upload).fillna("")
    if raw.empty:
        st.warning("The uploaded CSV has no rows.")
        return
    brand = st.text_input("Brand name", value="ABA Signal Pro")
    title = st.text_input("Report title", value="Daily Sports Analysis")
    limit = int(st.number_input("Max rows", min_value=1, max_value=500, value=min(75, len(raw)), step=1))
    rows = raw.head(limit).to_dict("records")
    for row in rows:
        row["report_brand_name"] = brand
        row["report_title"] = title
        row["report_language"] = "en"
    rows = enrich_rows_with_live_api_data(rows)
    preview = module.render_full_pick_magazine_page_png(rows[0], report_name=brand, page_number=1, total_pages=len(rows), language="en")
    pdf = module.render_full_magazine_book_pdf(rows, report_name=brand, language="en")
    st.download_button("Download Magazine PDF", pdf, file_name=f"{_safe(brand)}_magazine.pdf", mime="application/pdf")
    st.download_button("Download Preview PNG", preview, file_name=f"{_safe(brand)}_preview.png", mime="image/png")
    st.image(preview, caption="Generated magazine report preview", use_container_width=True)
    st.dataframe(raw.head(limit), use_container_width=True, hide_index=True)

"""Direct-page Streamlit branding patch.

This file is intentionally duplicated inside pages/ so it is picked up even when
Streamlit Cloud runs a page file directly instead of the repository root app.
"""

from __future__ import annotations

try:
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator
except Exception:  # pragma: no cover
    st = None
    DeltaGenerator = None

APP_NAME = "ABA Signal Pro"
APP_TAGLINE = "Powered by Reparodynamics"


def _label_key(label) -> str:
    return " ".join(str(label or "").lower().replace("%", "").replace("±", "").split())


if st is not None and DeltaGenerator is not None:
    _real_set_page_config = st.set_page_config
    _real_st_selectbox = st.selectbox
    _real_dg_selectbox = DeltaGenerator.selectbox

    def render_brand_once() -> None:
        if st.session_state.get("aba_direct_sidebar_brand_rendered"):
            return
        st.session_state["aba_direct_sidebar_brand_rendered"] = True
        with st.sidebar:
            st.markdown("## ABA Signal Pro")
            st.success("ABA")
            st.markdown("### Signal")
            st.error("Pro")
            st.caption(APP_TAGLINE)
            st.markdown("---")

    def patched_set_page_config(*args, **kwargs):
        if not args:
            kwargs.setdefault("page_title", APP_NAME)
            kwargs.setdefault("initial_sidebar_state", "expanded")
        result = _real_set_page_config(*args, **kwargs)
        try:
            render_brand_once()
        except Exception:
            pass
        return result

    def is_language_selector(label, options) -> bool:
        try:
            opts = list(options)
        except Exception:
            return False
        return _label_key(label) == "language / idioma" and "English" in opts and "Español" in opts

    def patched_st_selectbox(label, options, *args, **kwargs):
        if is_language_selector(label, options):
            render_brand_once()
        return _real_st_selectbox(label, options, *args, **kwargs)

    def patched_dg_selectbox(self, label, options, *args, **kwargs):
        if is_language_selector(label, options):
            render_brand_once()
        return _real_dg_selectbox(self, label, options, *args, **kwargs)

    st.set_page_config = patched_set_page_config
    st.selectbox = patched_st_selectbox
    DeltaGenerator.selectbox = patched_dg_selectbox

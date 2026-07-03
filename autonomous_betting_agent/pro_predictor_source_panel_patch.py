from __future__ import annotations


def install() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st, '_ABA_PRO_PREDICTOR_SOURCE_PANEL_PATCH', False):
        return
    old_subheader = st.subheader
    old_caption = st.caption

    def caption(body, *args, **kwargs):
        text = str(body or '')
        if text.startswith('App version: pro-predictor-v23'):
            body = 'App version: pro-predictor-v24-balldontlie-api-registry'
        return old_caption(body, *args, **kwargs)

    def subheader(body, *args, **kwargs):
        result = old_subheader(body, *args, **kwargs)
        if str(body or '').strip().lower() in {'api sources', 'fuentes api'} and not st.session_state.get('_aba_pro_predictor_bdl_source_visible'):
            st.session_state['_aba_pro_predictor_bdl_source_visible'] = True
            try:
                from autonomous_betting_agent.bdl_status import label as bdl_label
                status = bdl_label()
            except Exception:
                status = 'Missing'
            col, _, _ = st.columns(3)
            col.metric("Ball Don't Lie", status)
        return result

    st.caption = caption
    st.subheader = subheader
    st._ABA_PRO_PREDICTOR_SOURCE_PANEL_PATCH = True

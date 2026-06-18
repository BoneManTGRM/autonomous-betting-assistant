from __future__ import annotations

import builtins
import os
from typing import Any


def get_secret(*names: str) -> str:
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, '')).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret


def _running_in_ci() -> bool:
    return os.getenv('CI', '').lower() == 'true' or os.getenv('GITHUB_ACTIONS', '').lower() == 'true'


def _is_language_widget(label: Any, options: Any) -> bool:
    try:
        values = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return 'English' in values and 'Español' in values and ('language' in text or 'idioma' in text)


def _install_sidebar_fallback() -> None:
    if _running_in_ci():
        return
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
        from autonomous_betting_agent.sidebar_nav import APP_TAGLINE, SIDEBAR_CSS, normalize_language, render_tools_only
    except Exception:
        return
    if getattr(st, '_aba_sidebar_fallback_v12', False):
        return

    original_sidebar_radio = st.sidebar.radio
    original_sidebar_selectbox = st.sidebar.selectbox
    original_dg_radio = DeltaGenerator.radio
    original_dg_selectbox = DeltaGenerator.selectbox

    def _draw_prefix() -> None:
        if st.session_state.get('_aba_sidebar_rendered_v12'):
            return
        try:
            with st.sidebar:
                st.session_state['_aba_sidebar_rendered_v12'] = True
                st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
                st.markdown('### :green[ABA] Signal :red[Pro]')
                st.caption(APP_TAGLINE)
                st.markdown('---')
        except Exception:
            pass

    def _draw_tools(value: Any) -> None:
        if st.session_state.get('_aba_sidebar_tools_rendered_v12'):
            return
        try:
            with st.sidebar:
                st.session_state['_aba_sidebar_tools_rendered_v12'] = True
                render_tools_only(st, normalize_language(value))
        except Exception:
            pass

    def sidebar_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options) and not st.session_state.get('_aba_sidebar_rendered_v12'):
            _draw_prefix()
            kwargs['horizontal'] = True
            value = original_sidebar_radio('Language', options, *args, **kwargs)
            _draw_tools(value)
            return value
        return original_sidebar_radio(label, options, *args, **kwargs)

    def sidebar_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options) and not st.session_state.get('_aba_sidebar_rendered_v12'):
            _draw_prefix()
            value = original_sidebar_radio('Language', options, *args, horizontal=True, **kwargs)
            _draw_tools(value)
            return value
        return original_sidebar_selectbox(label, options, *args, **kwargs)

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options) and not st.session_state.get('_aba_sidebar_rendered_v12'):
            _draw_prefix()
            kwargs['horizontal'] = True
            value = original_dg_radio(self, 'Language', options, *args, **kwargs)
            _draw_tools(value)
            return value
        return original_dg_radio(self, label, options, *args, **kwargs)

    def dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options) and not st.session_state.get('_aba_sidebar_rendered_v12'):
            _draw_prefix()
            value = original_dg_radio(self, 'Language', options, *args, horizontal=True, **kwargs)
            _draw_tools(value)
            return value
        return original_dg_selectbox(self, label, options, *args, **kwargs)

    st.sidebar.radio = sidebar_radio
    st.sidebar.selectbox = sidebar_selectbox
    DeltaGenerator.radio = dg_radio
    DeltaGenerator.selectbox = dg_selectbox
    st._aba_sidebar_fallback_v12 = True


def _install_runtime_helpers() -> None:
    if _running_in_ci():
        return
    try:
        from autonomous_betting_agent.pro_predictor_defaults_patch import install_pro_predictor_defaults_patch
        install_pro_predictor_defaults_patch()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer
        install_odds_breakdown_normalizer()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.proof_dashboard_patch import install_proof_dashboard_patch
        install_proof_dashboard_patch()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.local_users import install_streamlit_local_user_selector
        install_streamlit_local_user_selector()
    except Exception:
        pass


_install_sidebar_fallback()
_install_runtime_helpers()

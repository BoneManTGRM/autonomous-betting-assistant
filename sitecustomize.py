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
    if getattr(st, '_aba_sidebar_fallback_v14', False):
        return

    original_sidebar_radio = st.sidebar.radio
    original_sidebar_selectbox = st.sidebar.selectbox
    original_sidebar_text_input = st.sidebar.text_input
    original_sidebar_caption = st.sidebar.caption
    original_dg_radio = DeltaGenerator.radio
    original_dg_selectbox = DeltaGenerator.selectbox
    original_dg_text_input = DeltaGenerator.text_input
    original_dg_caption = DeltaGenerator.caption

    def _shared_language() -> str:
        for key in ('global_language', 'app_language', 'learning_memory_language', 'pro_predictor_language', 'signal_board_language', 'odds_lock_pro_language'):
            value = st.session_state.get(key)
            if value in ('English', 'Español'):
                return value
        return 'English'

    def _draw_prefix() -> None:
        if st.session_state.get('_aba_sidebar_rendered_v14'):
            return
        try:
            with st.sidebar:
                st.session_state['_aba_sidebar_rendered_v14'] = True
                st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
                st.markdown('### :green[ABA] Signal :red[Pro]')
                st.caption(APP_TAGLINE)
                st.markdown('---')
        except Exception:
            pass

    def _draw_tools(value: Any) -> None:
        if st.session_state.get('_aba_sidebar_tools_rendered_v14'):
            return
        try:
            with st.sidebar:
                st.session_state['_aba_sidebar_tools_rendered_v14'] = True
                render_tools_only(st, normalize_language(value))
        except Exception:
            pass

    def _handle_language_widget(label: Any, options: Any, *args: Any, original: Any, self_obj: Any = None, **kwargs: Any) -> Any:
        if not _is_language_widget(label, options):
            if self_obj is None:
                return original(label, options, *args, **kwargs)
            return original(self_obj, label, options, *args, **kwargs)
        if st.session_state.get('_aba_sidebar_rendered_v14') or st.session_state.get('_aba_sidebar_rendered_v13') or st.session_state.get('_aba_sidebar_rendered_v12'):
            return _shared_language()
        _draw_prefix()
        kwargs['horizontal'] = True
        if self_obj is None:
            value = original_sidebar_radio('Language', options, *args, **kwargs)
        else:
            value = original_dg_radio(self_obj, 'Language', options, *args, **kwargs)
        _draw_tools(value)
        return value

    def sidebar_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return _handle_language_widget(label, options, *args, original=original_sidebar_radio, **kwargs)

    def sidebar_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return _handle_language_widget(label, options, *args, original=original_sidebar_selectbox, **kwargs)

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return _handle_language_widget(label, options, *args, original=original_dg_radio, self_obj=self, **kwargs)

    def dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return _handle_language_widget(label, options, *args, original=original_dg_selectbox, self_obj=self, **kwargs)

    def _is_test_window_label(label: Any) -> bool:
        text = str(label or '').strip().lower()
        return text in {'test window id', 'id de ventana de prueba'}

    def sidebar_text_input(label: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_test_window_label(label):
            return st.session_state.get(kwargs.get('key') or 'aba_test_window_id', kwargs.get('value', 'test_01'))
        return original_sidebar_text_input(label, *args, **kwargs)

    def dg_text_input(self: Any, label: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_test_window_label(label):
            return st.session_state.get(kwargs.get('key') or 'aba_test_window_id', kwargs.get('value', 'test_01'))
        return original_dg_text_input(self, label, *args, **kwargs)

    def sidebar_caption(body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or '').lower()
        if text.startswith('active test ledger') or text.startswith('ledger de prueba activo'):
            return st.empty()
        return original_sidebar_caption(body, *args, **kwargs)

    def dg_caption(self: Any, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or '').lower()
        if text.startswith('active test ledger') or text.startswith('ledger de prueba activo'):
            return self.empty()
        return original_dg_caption(self, body, *args, **kwargs)

    st.sidebar.radio = sidebar_radio
    st.sidebar.selectbox = sidebar_selectbox
    st.sidebar.text_input = sidebar_text_input
    st.sidebar.caption = sidebar_caption
    DeltaGenerator.radio = dg_radio
    DeltaGenerator.selectbox = dg_selectbox
    DeltaGenerator.text_input = dg_text_input
    DeltaGenerator.caption = dg_caption
    st._aba_sidebar_fallback_v14 = True


def _patch_ui_language_selector() -> None:
    if _running_in_ci():
        return
    try:
        import streamlit as st
        import autonomous_betting_agent.ui_language as ui_language
        from autonomous_betting_agent.sidebar_nav import render_app_sidebar
    except Exception:
        return
    if getattr(ui_language, '_aba_patched_render_language_selector_v14', False):
        return

    def render_language_selector(*, key: str) -> str:
        page_key = key.replace('_language', '')
        lang_code = render_app_sidebar(page_key, language_key=key, selector='radio')
        try:
            selected = 'Español' if lang_code == 'es' else 'English'
            st.session_state['app_language'] = selected
            st.session_state['global_language'] = selected
        except Exception:
            pass
        return lang_code

    ui_language.render_language_selector = render_language_selector
    ui_language._aba_patched_render_language_selector_v14 = True


def _install_runtime_helpers() -> None:
    if _running_in_ci():
        return
    try:
        from autonomous_betting_agent.mobile_button_fallback import install_mobile_button_fallback
        install_mobile_button_fallback()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.direct_pick_lock_patch import install_direct_pick_lock_patch
        install_direct_pick_lock_patch()
    except Exception:
        pass
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
_patch_ui_language_selector()
_install_runtime_helpers()

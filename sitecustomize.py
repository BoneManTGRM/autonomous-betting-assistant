from __future__ import annotations

import builtins
import os
from typing import Any

APP_TAGLINE = 'Powered by Reparodynamics'
LANGUAGE_KEYS = [
    'global_language',
    'pro_predictor_language',
    'signal_board_language',
    'threshold_optimizer_language',
    'what_are_the_odds_language',
    'what_are_the_odds_pro_language',
    'odds_lock_pro_language',
    'public_proof_dashboard_language',
    'learning_memory_language',
    'simulation_lab_language',
]
PAGE_LINKS = [
    ('Signal Board', 'pages/signal_board.py'),
    ('Pro Predictor', 'pages/pro_predictor.py'),
    ('Simulation Lab', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'pages/learn_memory.py'),
]


def get_secret(*names: str) -> str:
    try:
        import streamlit as st
    except Exception:
        st = None  # type: ignore[assignment]
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


def _shared_language(st: Any) -> str:
    for key in LANGUAGE_KEYS:
        value = st.session_state.get(key)
        if value in ('English', 'Español'):
            return value
    return 'English'


def _sync_language(st: Any, value: Any, *, active_key: str | None = None) -> None:
    if value not in ('English', 'Español'):
        return
    for key in LANGUAGE_KEYS:
        if key == active_key:
            continue
        try:
            st.session_state[key] = value
        except Exception:
            pass


def _prepare_language_kwargs(st: Any, options: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        values = list(options)
    except Exception:
        return kwargs
    if 'index' not in kwargs and 'English' in values and 'Español' in values:
        current = _shared_language(st)
        if current in values:
            kwargs = dict(kwargs)
            kwargs['index'] = values.index(current)
    kwargs['horizontal'] = True
    return kwargs


def _is_test_window_label(label: Any) -> bool:
    text = str(label or '').strip().lower()
    return text in {'test window id', 'id de ventana de prueba'}


def _is_active_test_caption(body: Any) -> bool:
    text = str(body or '').strip().lower()
    return text.startswith('active test ledger') or text.startswith('ledger de prueba activo')


def _render_brand_and_tools(st: Any) -> None:
    if getattr(st, '_aba_sidebar_explicit_rendering', False):
        return
    try:
        with st.sidebar:
            st.markdown('### :green[ABA] Signal :red[Pro]')
            st.caption(APP_TAGLINE)
            st.markdown('---')
    except Exception:
        pass


def _render_tools(st: Any) -> None:
    if getattr(st, '_aba_sidebar_explicit_rendering', False):
        return
    try:
        lang = _shared_language(st)
        with st.sidebar:
            st.markdown('---')
            st.markdown('### ' + ('Herramientas' if lang == 'Español' else 'Tools'))
            for label, path in PAGE_LINKS:
                try:
                    st.page_link(path, label=label)
                except Exception:
                    st.caption(label)
    except Exception:
        pass


def _install_sidebar_safety_hooks() -> None:
    if _running_in_ci():
        return
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_sidebar_safety_hooks_v10', False):
        return

    original_sidebar_radio = st.sidebar.radio
    original_sidebar_selectbox = st.sidebar.selectbox
    original_sidebar_text_input = st.sidebar.text_input
    original_sidebar_caption = st.sidebar.caption
    original_dg_radio = DeltaGenerator.radio
    original_dg_selectbox = DeltaGenerator.selectbox
    original_dg_text_input = DeltaGenerator.text_input
    original_dg_caption = DeltaGenerator.caption

    def sidebar_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options):
            _render_brand_and_tools(st)
            kwargs = _prepare_language_kwargs(st, options, kwargs)
            value = original_sidebar_radio(label, options, *args, **kwargs)
            _sync_language(st, value, active_key=kwargs.get('key'))
            _render_tools(st)
            return value
        return original_sidebar_radio(label, options, *args, **kwargs)

    def sidebar_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options):
            _render_brand_and_tools(st)
            kwargs = _prepare_language_kwargs(st, options, kwargs)
            # Force legacy selectboxes into a compact radio-style control.
            value = original_sidebar_radio(label, options, *args, **kwargs)
            _sync_language(st, value, active_key=kwargs.get('key'))
            _render_tools(st)
            return value
        return original_sidebar_selectbox(label, options, *args, **kwargs)

    def sidebar_text_input(label: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_test_window_label(label):
            key = kwargs.get('key') or 'aba_test_window_id'
            default = kwargs.get('value', 'test_01')
            return st.session_state.get(key, st.session_state.get('aba_test_window_id', default))
        return original_sidebar_text_input(label, *args, **kwargs)

    def sidebar_caption(body: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_active_test_caption(body):
            return st.empty()
        return original_sidebar_caption(body, *args, **kwargs)

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options) and not getattr(st, '_aba_sidebar_explicit_rendering', False):
            _render_brand_and_tools(st)
            kwargs = _prepare_language_kwargs(st, options, kwargs)
            value = original_dg_radio(self, label, options, *args, **kwargs)
            _sync_language(st, value, active_key=kwargs.get('key'))
            _render_tools(st)
            return value
        return original_dg_radio(self, label, options, *args, **kwargs)

    def dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_widget(label, options) and not getattr(st, '_aba_sidebar_explicit_rendering', False):
            _render_brand_and_tools(st)
            kwargs = _prepare_language_kwargs(st, options, kwargs)
            value = original_dg_radio(self, label, options, *args, **kwargs)
            _sync_language(st, value, active_key=kwargs.get('key'))
            _render_tools(st)
            return value
        return original_dg_selectbox(self, label, options, *args, **kwargs)

    def dg_text_input(self: Any, label: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_test_window_label(label):
            key = kwargs.get('key') or 'aba_test_window_id'
            default = kwargs.get('value', 'test_01')
            return st.session_state.get(key, st.session_state.get('aba_test_window_id', default))
        return original_dg_text_input(self, label, *args, **kwargs)

    def dg_caption(self: Any, body: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_active_test_caption(body):
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
    st._aba_sidebar_safety_hooks_v10 = True


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


_install_sidebar_safety_hooks()
_install_runtime_helpers()

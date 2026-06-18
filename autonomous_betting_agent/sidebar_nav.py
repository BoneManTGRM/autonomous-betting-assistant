from __future__ import annotations

from typing import Any

APP_TAGLINE = 'Powered by Reparodynamics'
LANGUAGE_KEYS = [
    'global_language',
    'signal_board_language',
    'pro_predictor_language',
    'threshold_optimizer_language',
    'what_are_the_odds_language',
    'what_are_the_odds_pro_language',
    'odds_lock_pro_language',
    'public_proof_dashboard_language',
    'learning_memory_language',
    'simulation_lab_language',
]
TOOLS: tuple[tuple[str, str, str], ...] = (
    ('Signal Board', 'Signal Board', 'pages/signal_board.py'),
    ('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor.py'),
    ('Simulation Lab', 'Laboratorio de Simulación', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'Optimizador de Umbral', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'What Are the Odds', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'Odds Lock Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'Dashboard Público de Prueba', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'Memoria de Aprendizaje', 'pages/learn_memory.py'),
)


def normalize_language(value: Any) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def _current_language(st: Any) -> str:
    for key in LANGUAGE_KEYS:
        value = st.session_state.get(key)
        if value in ('English', 'Español'):
            return value
    return 'English'


def _sync_language(st: Any, value: str, *, current_key: str | None = None) -> None:
    if value not in ('English', 'Español'):
        value = 'English'
    for key in LANGUAGE_KEYS:
        if key == current_key:
            continue
        try:
            st.session_state[key] = value
        except Exception:
            pass


def render_app_sidebar(page_key: str, *, language_key: str | None = None, selector: str = 'radio') -> str:
    import streamlit as st

    key = language_key or f'{page_key}_language'
    current = _current_language(st)
    index = 1 if current == 'Español' else 0
    with st.sidebar:
        st.markdown('### :green[ABA] Signal :red[Pro]')
        st.caption(APP_TAGLINE)
        st.markdown('---')
        if selector == 'selectbox':
            value = st.selectbox('Language / Idioma', ['English', 'Español'], index=index, key=key)
        else:
            value = st.radio('Language', ['English', 'Español'], index=index, key=key, horizontal=True)
        _sync_language(st, value, current_key=key)
        lang = normalize_language(value)
        st.markdown('---')
        st.markdown('### ' + ('Herramientas' if lang == 'es' else 'Tools'))
        for english, spanish, path in TOOLS:
            label = spanish if lang == 'es' else english
            try:
                st.page_link(path, label=label)
            except Exception:
                st.caption(label)
    return lang


def render_sidebar_nav(language: Any = 'en', *, show_workflow: bool = False) -> None:
    import streamlit as st

    lang = normalize_language(language)
    st.sidebar.markdown('---')
    st.sidebar.markdown('### ' + ('Herramientas' if lang == 'es' else 'Tools'))
    for english, spanish, path in TOOLS:
        label = spanish if lang == 'es' else english
        try:
            st.sidebar.page_link(path, label=label)
        except Exception:
            st.sidebar.caption(label)

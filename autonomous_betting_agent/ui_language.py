from __future__ import annotations

import streamlit as st

SESSION_KEY = 'app_language'
OPTIONS = ['English', 'Español']


def _code(value: object) -> str:
    text = str(value or 'English').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def label(value: object = None) -> str:
    return 'Español' if _code(value if value is not None else st.session_state.get(SESSION_KEY, 'English')) == 'es' else 'English'


def query_param_language() -> str | None:
    try:
        raw = st.query_params.get('lang')
    except Exception:
        return None
    if not raw:
        return None
    return label(raw)


def set_global_language(selected: object) -> str:
    normalized = label(selected)
    st.session_state[SESSION_KEY] = normalized
    st.session_state['global_language'] = normalized
    try:
        st.query_params['lang'] = 'es' if normalized == 'Español' else 'en'
    except Exception:
        pass
    return normalized


def render_language_selector(*, key: str) -> str:
    current = query_param_language() or st.session_state.get(key) or st.session_state.get('global_language') or st.session_state.get(SESSION_KEY, 'English')
    current = label(current)
    selected = st.sidebar.selectbox('Language / Idioma', OPTIONS, index=OPTIONS.index(current), key=key)
    set_global_language(selected)
    return _code(selected)

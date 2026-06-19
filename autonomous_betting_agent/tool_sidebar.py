from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

APP_TAGLINE = 'Powered by Reparodynamics'
LANGUAGE_KEYS = (
    'global_language',
    'app_language',
    'simulation_lab_language',
    'signal_board_language',
    'pro_predictor_language',
    'threshold_optimizer_language',
    'what_are_the_odds_language',
    'what_are_the_odds_pro_language',
    'odds_lock_pro_language',
    'public_proof_dashboard_language',
    'learning_memory_language',
)
TOOLS: tuple[tuple[str, str], ...] = (
    ('Signal Board', 'pages/signal_board.py'),
    ('Pro Predictor', 'pages/pro_predictor.py'),
    ('Simulation Lab', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'pages/learn_memory.py'),
)
SIDEBAR_CSS = '''
<style>
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1.4rem; }
section[data-testid="stSidebar"] a[href*="pages/"] {
  display:block; padding:.62rem .82rem; border-radius:.75rem; margin:.18rem 0;
  text-decoration:none!important; font-weight:650;
}
section[data-testid="stSidebar"] a[href*="pages/"]:hover { background:rgba(255,255,255,.10); }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 { margin-top:.65rem; }
</style>
'''


def normal_language(value: object) -> str:
    text = str(value or '').lower()
    return 'Español' if text.startswith('es') or 'español' in text or 'espanol' in text else 'English'


def language_code(value: object) -> str:
    return 'es' if normal_language(value) == 'Español' else 'en'


def current_language(default: str = 'English') -> str:
    for key in LANGUAGE_KEYS:
        try:
            value = st.session_state.get(key)
        except Exception:
            value = None
        if value in ('English', 'Español'):
            return str(value)
    return normal_language(default)


def sync_language(st_module: Any, value: object) -> str:
    lang = normal_language(value)
    for key in LANGUAGE_KEYS:
        try:
            st_module.session_state[key] = lang
        except Exception:
            pass
    return lang


def is_language_widget(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return 'English' in opts and 'Español' in opts and ('language' in text or 'idioma' in text)


def _install_language_selectbox_suppressor() -> None:
    """Hide legacy sidebar language selectboxes used by old pages.

    Simulation Lab still calls ``st.sidebar.selectbox('Language / Idioma', ...)``
    before drawing the shared sidebar. That produced the one-off broken layout
    shown on mobile. This suppresses only that legacy language selectbox and
    leaves file uploaders, buttons, forms, and normal selectboxes untouched.
    """
    if getattr(st.sidebar, '_aba_language_selectbox_suppressed_v1', False):
        return
    original_selectbox = st.sidebar.selectbox

    def patched_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_widget(label, options):
            key = kwargs.get('key')
            value = current_language(kwargs.get('value', 'English'))
            if key:
                try:
                    st.session_state[key] = value
                except Exception:
                    pass
            return value
        return original_selectbox(label, options, *args, **kwargs)

    st.sidebar.selectbox = patched_selectbox
    st.sidebar._aba_language_selectbox_suppressed_v1 = True


def inject_sidebar_css(st_module: Any) -> None:
    try:
        st_module.sidebar.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
    except Exception:
        pass


def render_sidebar_brand(st_module: Any) -> None:
    st_module.sidebar.markdown('### :green[ABA] Signal :red[Pro]')
    st_module.sidebar.caption(APP_TAGLINE)


def render_tools_only(st_module: Any) -> None:
    st_module.sidebar.markdown('---')
    st_module.sidebar.markdown('### Tools')
    for label, path in TOOLS:
        try:
            st_module.sidebar.page_link(path, label=label)
        except Exception:
            st_module.sidebar.caption(label)


def render_curated_sidebar(st_module: Any, language: object = 'English', *, page_key: str = 'app') -> None:
    inject_sidebar_css(st_module)
    render_sidebar_brand(st_module)
    st_module.sidebar.markdown('---')
    current = normal_language(language or current_language())
    index = 1 if current == 'Español' else 0
    selected = st_module.sidebar.radio('Language', ['English', 'Español'], index=index, key=f'{page_key}_language', horizontal=True)
    sync_language(st_module, selected)
    render_tools_only(st_module)


def sidebar_language_selector(st_module: Any, *, key: str, default: str = 'English') -> str:
    try:
        value = st_module.session_state.get(key, st_module.session_state.get('global_language', default))
    except Exception:
        value = default
    return language_code(value)


def render_tool_sidebar(page_key: str, language: str = 'English') -> None:
    render_curated_sidebar(st, language, page_key=page_key)


def install_sidebar_tools() -> None:
    return None


def session_state_summary() -> pd.DataFrame:
    return pd.DataFrame()


def proof_sidebar_snapshot() -> dict[str, int]:
    return {'pro_predictor_rows': 0, 'high_confidence_rows': 0, 'locked_rows': 0}


_install_language_selectbox_suppressor()

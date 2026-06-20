from __future__ import annotations

import base64
import html
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
    ('Storage Diagnostics', 'Diagnóstico de Almacenamiento', 'pages/storage_diagnostics.py'),
    ('Learning Memory', 'Memoria de Aprendizaje', 'pages/learn_memory.py'),
)
PRO_PREDICTOR_LARGE_LIST_70_DEFAULTS = {
    'baseline_accuracy_min_books': 1,
    'baseline_accuracy_min_model_prob': 0.58,
    'baseline_accuracy_min_edge': -0.03,
    'baseline_accuracy_strong_edge': 0.04,
    'baseline_accuracy_min_strength': 38.0,
    'baseline_accuracy_use_high_conf': True,
    'baseline_accuracy_max_high_conf': 300,
    'baseline_accuracy_min_high_prob': 0.58,
    'baseline_accuracy_min_high_edge': -0.03,
    'baseline_accuracy_min_high_strength': 38.0,
    'baseline_accuracy_min_high_agent': 35.0,
}
SIDEBAR_CSS = '''
<style>
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1.4rem; }
section[data-testid="stSidebar"] a[href*="pages/"] {
  display: block; padding: .62rem .82rem; border-radius: .75rem; margin: .18rem 0;
  text-decoration: none !important; font-weight: 650;
}
section[data-testid="stSidebar"] a[href*="pages/"]:hover { background: rgba(255,255,255,.10); }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 { margin-top: .65rem; }
.aba-safe-download {
  display:inline-block; padding:.65rem 1rem; border-radius:.7rem; background:#ef5350; color:#fff!important;
  text-decoration:none!important; font-weight:700; margin:.35rem 0;
}
</style>
'''


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


def _tool_label(english: str, spanish: str, lang: str) -> str:
    return spanish if lang == 'es' else english


def _install_safe_download_button(st_module: Any) -> None:
    try:
        if getattr(st_module, '_aba_safe_download_button_installed', False):
            return
        original = getattr(st_module, 'download_button', None)

        def safe_download_button(label: str, data: Any = '', file_name: str | None = None, mime: str | None = None, *args: Any, **kwargs: Any) -> bool:
            name = file_name or 'download.csv'
            media_type = mime or 'text/csv'
            if isinstance(data, bytes):
                payload = data
            else:
                payload = str(data or '').encode('utf-8')
            if len(payload) > 1_500_000:
                st_module.warning('Download is too large for the mobile-safe link. Reduce rows or copy from the table.')
                return False
            encoded = base64.b64encode(payload).decode('ascii')
            safe_label = html.escape(str(label))
            safe_name = html.escape(str(name), quote=True)
            safe_mime = html.escape(str(media_type), quote=True)
            st_module.markdown(
                f'<a class="aba-safe-download" download="{safe_name}" href="data:{safe_mime};base64,{encoded}">{safe_label}</a>',
                unsafe_allow_html=True,
            )
            return False

        setattr(st_module, '_aba_original_download_button', original)
        setattr(st_module, 'download_button', safe_download_button)
        setattr(st_module, '_aba_safe_download_button_installed', True)
    except Exception:
        pass


def _apply_page_defaults(st: Any, page_key: str) -> None:
    _install_safe_download_button(st)
    if page_key != 'pro_predictor':
        return
    try:
        for key, value in PRO_PREDICTOR_LARGE_LIST_70_DEFAULTS.items():
            st.session_state[key] = value
        st.session_state['_large_list_70_defaults_forced_v4'] = True
    except Exception:
        pass
    try:
        from .pro_predictor_defaults_patch import apply_large_list_70_defaults
        apply_large_list_70_defaults(st)
    except Exception:
        pass


def render_tools_only(st: Any, lang: str) -> None:
    st.markdown('---')
    st.markdown('### ' + ('Herramientas' if lang == 'es' else 'Tools'))
    for english, spanish, path in TOOLS:
        try:
            st.page_link(path, label=_tool_label(english, spanish, lang))
        except Exception:
            st.caption(_tool_label(english, spanish, lang))


def render_app_sidebar(page_key: str, *, language_key: str | None = None, selector: str = 'radio') -> str:
    import streamlit as st

    _apply_page_defaults(st, page_key)
    key = language_key or f'{page_key}_language'
    current = _current_language(st)
    index = 1 if current == 'Español' else 0
    with st.sidebar:
        st.session_state['_aba_sidebar_rendered_clean_v1'] = True
        st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
        st.markdown('### :green[ABA] Signal :red[Pro]')
        st.caption(APP_TAGLINE)
        st.markdown('---')
        value = st.radio('Language', ['English', 'Español'], index=index, key=key, horizontal=True)
        _sync_language(st, value, current_key=key)
        lang = normalize_language(value)
        render_tools_only(st, lang)
    return lang


def render_sidebar_nav(language: Any = 'en', *, show_workflow: bool = False) -> None:
    import streamlit as st

    _install_safe_download_button(st)
    lang = normalize_language(language)
    st.sidebar.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
    render_tools_only(st.sidebar, lang)

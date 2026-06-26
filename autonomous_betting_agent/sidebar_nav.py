from __future__ import annotations

import base64
import html
from typing import Any

APP_TAGLINE = 'Powered by Reparodynamics'
APP_TAGLINE_ES = 'Impulsado por Reparodynamics'
GLOBAL_LANGUAGE_KEY = 'aba_global_language'
LANGUAGE_KEYS = ['global_language','signal_board_language','pro_predictor_language','odds_lock_pro_language','report_studio_language','proof_center_language','local_control_center_language','learning_memory_language','storage_diagnostics_language','reset_storage_language']
TOOLS: tuple[tuple[str, str, str], ...] = (
    ('Signal Board', 'Panel de Señales', 'pages/signal_board.py'),
    ('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor_volume.py'),
    ('Odds Lock Pro', 'Bloqueo de Cuotas Pro', 'pages/odds_lock_pro.py'),
    ('Report Studio', 'Estudio de Reportes', 'pages/report_studio.py'),
    ('Proof Center', 'Centro de Prueba', 'pages/proof_center.py'),
    ('Local Control Center', 'Centro de Control Local', 'pages/local_control_center.py'),
    ('Learning Memory', 'Memoria de Aprendizaje', 'pages/learn_memory_safe.py'),
    ('Storage Diagnostics', 'Diagnóstico de Almacenamiento', 'pages/storage_diagnostics.py'),
    ('Reset Storage', 'Reiniciar almacenamiento', 'pages/reset_storage.py'),
)
REPARODYNAMICS_PAGE = ('Reparodynamics', 'Reparodynamics', 'pages/reparodynamics.py')
PRO_PREDICTOR_LARGE_LIST_70_DEFAULTS = {'baseline_accuracy_min_books': 1,'baseline_accuracy_min_model_prob': 0.58,'baseline_accuracy_min_edge': -0.03,'baseline_accuracy_strong_edge': 0.04,'baseline_accuracy_min_strength': 38.0,'baseline_accuracy_use_high_conf': True,'baseline_accuracy_max_high_conf': 700,'baseline_accuracy_min_high_prob': 0.58,'baseline_accuracy_min_high_edge': -0.03,'baseline_accuracy_min_high_strength': 38.0,'baseline_accuracy_min_high_agent': 35.0}
SIDEBAR_CSS = '''
<style>
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1.4rem; }
section[data-testid="stSidebar"] a[href*="pages/"] { display: block; padding: .62rem .82rem; border-radius: .75rem; margin: .18rem 0; text-decoration: none !important; font-weight: 650; }
section[data-testid="stSidebar"] a[href*="pages/"]:hover { background: rgba(255,255,255,.10); }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 { margin-top: .65rem; }
.aba-sidebar-title { font-size: 1.45rem; line-height: 1.2; font-weight: 850; margin: .35rem 0 .25rem 0; background: linear-gradient(90deg, #f6d365 0%, #fda085 40%, #70e1f5 100%); -webkit-background-clip: text; background-clip: text; color: transparent; }
.aba-sidebar-tagline { color: rgba(255,255,255,.62); margin-bottom: 1rem; }
.aba-safe-download { display:inline-block; padding:.65rem 1rem; border-radius:.7rem; background:#ef5350; color:#fff!important; text-decoration:none!important; font-weight:700; margin:.35rem 0; }
</style>
'''
GLOBAL_UPLOAD_ES_CSS = '''
<style>
div[data-testid="stFileUploader"] button,
div[data-testid="stFileUploader"] button * {
  font-size: 0 !important;
  line-height: 0 !important;
}
div[data-testid="stFileUploader"] button::after {
  content: "Subir";
  font-size: 1rem !important;
  line-height: 1.2 !important;
  white-space: nowrap !important;
}
body div[data-testid="stFileUploader"] button div p::after,
body div[data-testid="stFileUploader"] button p::after,
body div[data-testid="stFileUploader"] button span::after,
body div[data-testid="stFileUploader"] button *::after {
  content: none !important;
  display: none !important;
}
div[data-testid="stFileUploader"] [data-testid="stFileUploaderFileName"],
div[data-testid="stFileUploader"] small {
  font-size: 0 !important;
}
div[data-testid="stFileUploader"] small::after {
  content: "Archivo compatible";
  font-size: .9rem !important;
}
div[data-testid="stFileUploader"] section > div > span,
div[data-testid="stFileUploader"] section > div > div > span {
  font-size: 0 !important;
}
div[data-testid="stFileUploader"] section > div > span::after,
div[data-testid="stFileUploader"] section > div > div > span::after {
  content: "200 MB por archivo";
  font-size: .9rem !important;
}
</style>
'''


def normalize_language(value: Any) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def _language_label(value: Any) -> str:
    return 'Español' if normalize_language(value) == 'es' else 'English'


def _current_language(st: Any) -> str:
    value = st.session_state.get(GLOBAL_LANGUAGE_KEY)
    if value in ('English', 'Español'):
        return value
    for key in LANGUAGE_KEYS:
        value = st.session_state.get(key)
        if value in ('English', 'Español'):
            return value
    return 'English'


def _sync_global_from_radio(widget_key: str) -> None:
    import streamlit as st
    language = _language_label(st.session_state.get(widget_key, st.session_state.get(GLOBAL_LANGUAGE_KEY, 'English')))
    st.session_state[GLOBAL_LANGUAGE_KEY] = language


def _label(item: tuple[str, str, str], language: str) -> str:
    return item[1] if normalize_language(language) == 'es' else item[0]


def _render_page_link(st: Any, item: tuple[str, str, str], language: str, current_page: str) -> None:
    label = _label(item, language)
    path = item[2]
    safe_label = html.escape(label)
    if current_page and current_page in path:
        st.markdown(f'**● {safe_label}**')
    else:
        st.page_link(path, label=label)


def render_app_sidebar(current_page: str, *, language_key: str = 'global_language', selector: str = 'radio') -> str:
    import streamlit as st
    language = _language_label(_current_language(st))
    widget_key = f'aba_radio_{language_key}'
    if widget_key not in st.session_state:
        st.session_state[widget_key] = language
    if normalize_language(language) == 'es':
        st.markdown(GLOBAL_UPLOAD_ES_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
        st.markdown('<div class="aba-sidebar-title">ABA Signal Pro</div>', unsafe_allow_html=True)
        tagline = APP_TAGLINE if language == 'English' else APP_TAGLINE_ES
        st.markdown(f'<div class="aba-sidebar-tagline">{html.escape(tagline)}</div>', unsafe_allow_html=True)
        language = st.radio('Language / Idioma', ['English', 'Español'], key=widget_key, horizontal=True, on_change=_sync_global_from_radio, args=(widget_key,))
        st.session_state[GLOBAL_LANGUAGE_KEY] = language
        if normalize_language(language) == 'es':
            st.markdown(GLOBAL_UPLOAD_ES_CSS, unsafe_allow_html=True)
        st.markdown('---')
        for item in TOOLS:
            _render_page_link(st, item, language, current_page)
        _render_page_link(st, REPARODYNAMICS_PAGE, language, current_page)
    return normalize_language(language)


def safe_csv_download(label: str, csv_text: str, filename: str) -> str:
    payload = base64.b64encode(str(csv_text or '').encode('utf-8')).decode('ascii')
    return f'<a class="aba-safe-download" download="{html.escape(filename)}" href="data:text/csv;base64,{payload}">{html.escape(label)}</a>'
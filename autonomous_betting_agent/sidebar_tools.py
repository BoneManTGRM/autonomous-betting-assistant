from __future__ import annotations

from typing import Any

APP_NAME = 'ARA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'

PAGES = (
    ('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor.py'),
    ('Ultra 70 Profit Mode', 'Ultra 70 Profit Mode', 'pages/ultra80_profit_mode.py'),
    ('Simulation Lab', 'Laboratorio de Simulación', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'Optimizador de Umbrales', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'Cuotas y Valor', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'Bloqueo de Cuotas Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'Dashboard Público de Prueba', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'Memoria de Aprendizaje', 'pages/learn_memory.py'),
    ('Reset Lock File', 'Reiniciar Archivo de Bloqueo', 'pages/reset_lock_file.py'),
)

LANG_KEYS = (
    'global_language', 'app_language', 'simulation_lab_language', 'pro_predictor_language',
    'ultra80_profit_mode_language', 'odds_lock_pro_language', 'public_proof_dashboard_language',
    'reset_lock_file_language', 'learn_memory_language', 'learning_memory_language',
    'threshold_optimizer_language', 'what_are_the_odds_language', 'what_are_the_odds_pro_language',
)

CSS = '''
<style>
[data-testid="stSidebarNav"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"],
section[data-testid="stSidebar"] nav[aria-label="Page navigation"],
section[data-testid="stSidebar"] nav[aria-label="pages"],
section[data-testid="stSidebar"] nav[aria-label="Pages"] {
    display: none !important;
    height: 0 !important;
    max-height: 0 !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="collapsedControl"] { z-index: 999999 !important; }
@media(max-width:900px){
    section[data-testid="stSidebar"]{
        width:min(86vw,360px)!important;
        min-width:min(86vw,360px)!important;
        max-width:min(86vw,360px)!important;
        box-shadow:0 0 0 9999px rgba(0,0,0,.32)!important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{
        padding-top:.75rem!important;
        padding-left:.9rem!important;
        padding-right:.9rem!important;
    }
    .block-container{
        padding-left:.85rem!important;
        padding-right:.85rem!important;
        max-width:100vw!important;
    }
}
</style>
'''


def normal_language(value: object) -> str:
    text = str(value or '').strip().lower()
    return 'Español' if text.startswith('es') or 'español' in text or 'espanol' in text else 'English'


def language_code(value: object) -> str:
    return 'es' if normal_language(value) == 'Español' else 'en'


def sync_language(st: Any, value: object) -> str:
    language = normal_language(value)
    for key in LANG_KEYS:
        try:
            st.session_state[key] = language
        except Exception:
            pass
    return language


def is_language_widget(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    label_text = str(label or '').lower()
    return 'English' in opts and 'Español' in opts and ('language' in label_text or 'idioma' in label_text)


def inject_sidebar_css(st: Any) -> None:
    try:
        st.markdown(CSS, unsafe_allow_html=True)
    except Exception:
        pass


def render_curated_sidebar(st: Any, language: object = 'English') -> None:
    language = normal_language(language)
    tools_label = 'Herramientas' if language == 'Español' else 'Tools'
    workflow_label = 'Flujo de trabajo' if language == 'Español' else 'Workflow'
    if language == 'Español':
        workflow = 'Predictor Pro → Máxima Confianza → Odds Lock Pro → Dashboard Público → Memoria de Aprendizaje.'
        detail = 'Odds Lock Pro bloquea picks con timestamp; Dashboard Público muestra ROI y resultados.'
    else:
        workflow = 'Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory.'
        detail = 'Odds Lock Pro timestamps locked picks; Public Proof Dashboard shows ROI and results.'
    with st.sidebar:
        st.divider()
        st.markdown('### :green[ARA] Signal :red[Pro]')
        st.caption(APP_TAGLINE)
        st.divider()
        st.subheader(tools_label)
        for english, spanish, path in PAGES:
            label = spanish if language == 'Español' else english
            try:
                st.page_link(path, label=label)
            except Exception:
                st.caption(label)
        st.divider()
        st.subheader(workflow_label)
        st.caption(workflow)
        st.caption(detail)


def sidebar_language_selector(st: Any, *, key: str, default: str = 'English') -> str:
    inject_sidebar_css(st)
    current = normal_language(st.session_state.get(key, st.session_state.get('global_language', default)))
    options = ['English', 'Español']
    index = options.index(current) if current in options else 0
    selected = st.sidebar.radio('Idioma' if current == 'Español' else 'Language', options, index=index, key=key, horizontal=True)
    language = sync_language(st, selected)
    render_curated_sidebar(st, language)
    return language_code(language)


def install_sidebar_tools() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_ara_sidebar_safety_v8', False):
        return
    st._ara_sidebar_safety_v8 = True

    original_set_page_config = st.set_page_config
    original_markdown = st.markdown
    original_st_radio = st.radio
    original_st_selectbox = st.selectbox
    original_sidebar_radio = st.sidebar.radio
    original_sidebar_selectbox = st.sidebar.selectbox
    original_dg_radio = getattr(DeltaGenerator, 'radio', None)
    original_dg_selectbox = DeltaGenerator.selectbox

    def inject_css() -> None:
        try:
            original_markdown(CSS, unsafe_allow_html=True)
        except Exception:
            pass

    def page_config(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault('initial_sidebar_state', 'expanded')
        result = original_set_page_config(*args, **kwargs)
        inject_css()
        return result

    def after_language(value: object) -> object:
        language = sync_language(st, value)
        render_curated_sidebar(st, language)
        return value

    def language_as_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        opts = list(options)
        requested_key = kwargs.get('key')
        current = normal_language(st.session_state.get(requested_key or 'global_language', st.session_state.get('global_language', 'English')))
        index = opts.index(current) if current in opts else 0
        clean_kwargs = {k: v for k, v in kwargs.items() if k in {'key', 'help', 'disabled', 'label_visibility', 'captions'}}
        clean_kwargs['horizontal'] = True
        clean_kwargs['index'] = index
        value = original_sidebar_radio('Idioma' if current == 'Español' else 'Language', opts, *args, **clean_kwargs)
        return after_language(value)

    def sidebar_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_widget(label, options):
            value = original_sidebar_radio(label, options, *args, **kwargs)
            return after_language(value)
        return original_sidebar_radio(label, options, *args, **kwargs)

    def sidebar_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_widget(label, options):
            return language_as_radio(label, options, *args, **kwargs)
        return original_sidebar_selectbox(label, options, *args, **kwargs)

    def st_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = original_st_radio(label, options, *args, **kwargs)
        if is_language_widget(label, options):
            after_language(value)
        return value

    def st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = original_st_selectbox(label, options, *args, **kwargs)
        if is_language_widget(label, options):
            after_language(value)
        return value

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_widget(label, options):
            value = original_dg_radio(self, label, options, *args, **kwargs) if original_dg_radio else original_st_radio(label, options, *args, **kwargs)
            return after_language(value)
        return original_dg_radio(self, label, options, *args, **kwargs) if original_dg_radio else original_st_radio(label, options, *args, **kwargs)

    def dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_widget(label, options):
            return language_as_radio(label, options, *args, **kwargs)
        return original_dg_selectbox(self, label, options, *args, **kwargs)

    st.set_page_config = page_config
    st.radio = st_radio
    st.selectbox = st_selectbox
    try:
        st.sidebar.radio = sidebar_radio
        st.sidebar.selectbox = sidebar_selectbox
    except Exception:
        pass
    if original_dg_radio is not None:
        DeltaGenerator.radio = dg_radio
    DeltaGenerator.selectbox = dg_selectbox
    inject_css()

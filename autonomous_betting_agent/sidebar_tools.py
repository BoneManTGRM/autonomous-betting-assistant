from __future__ import annotations

from typing import Any

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
LANG_KEYS = ('global_language','app_language','pro_predictor_language','ultra80_profit_mode_language','simulation_lab_language','threshold_optimizer_language','what_are_the_odds_language','what_are_the_odds_pro_language','odds_lock_pro_language','public_proof_dashboard_language','reset_lock_file_language','learn_memory_language','learning_memory_language')
SIDEBAR_RENDERED_KEY = '_ara_curated_sidebar_rendered_this_script_run'
CSS = '''
<style>
[data-testid="stSidebarNav"],section[data-testid="stSidebar"] [data-testid="stSidebarNav"],section[data-testid="stSidebar"] nav[aria-label="Page navigation"],section[data-testid="stSidebar"] nav[aria-label="pages"],section[data-testid="stSidebar"] nav[aria-label="Pages"]{display:none!important;height:0!important;max-height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;}
[data-testid="collapsedControl"]{z-index:999999!important;}
@media(max-width:900px){section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding:.75rem .9rem!important;overflow-x:hidden!important}.block-container{padding-left:.85rem!important;padding-right:.85rem!important;max-width:100vw!important}}
</style>
'''


def normal_language(value: object) -> str:
    text = str(value or '').lower()
    return 'Español' if text.startswith('es') or 'español' in text or 'espanol' in text else 'English'


def sync_language(st: Any, value: object) -> str:
    lang = normal_language(value)
    for key in LANG_KEYS:
        try:
            st.session_state[key] = lang
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


def inject_sidebar_css(st: Any) -> None:
    try:
        st.markdown(CSS, unsafe_allow_html=True)
    except Exception:
        pass


def reset_sidebar_render_guard(st: Any) -> None:
    try:
        st.session_state[SIDEBAR_RENDERED_KEY] = False
    except Exception:
        pass


def render_curated_sidebar(st: Any, language: object = 'English') -> None:
    try:
        if st.session_state.get(SIDEBAR_RENDERED_KEY):
            return
        st.session_state[SIDEBAR_RENDERED_KEY] = True
    except Exception:
        pass
    lang = normal_language(language)
    with st.sidebar:
        st.divider()
        st.markdown('### :green[ARA] Signal :red[Pro]')
        st.caption(APP_TAGLINE)
        st.divider()
        st.subheader('Herramientas' if lang == 'Español' else 'Tools')
        for en, es, path in PAGES:
            try:
                st.page_link(path, label=es if lang == 'Español' else en)
            except Exception:
                st.caption(es if lang == 'Español' else en)
        st.divider()
        st.subheader('Flujo de trabajo' if lang == 'Español' else 'Workflow')
        st.caption('Predictor Pro → Máxima Confianza → Odds Lock Pro → Dashboard Público → Memoria de Aprendizaje.' if lang == 'Español' else 'Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory.')
        st.caption('Odds Lock Pro bloquea picks con timestamp; Dashboard Público muestra ROI y resultados.' if lang == 'Español' else 'Odds Lock Pro timestamps locked picks; Public Proof Dashboard shows ROI and results.')


def sidebar_language_selector(st: Any, *, key: str, default: str = 'English') -> str:
    inject_sidebar_css(st)
    current = normal_language(st.session_state.get(key, st.session_state.get('global_language', default)))
    options = ['English', 'Español']
    selected = st.sidebar.radio('Idioma' if current == 'Español' else 'Language', options, index=options.index(current), key=key, horizontal=True)
    lang = sync_language(st, selected)
    return 'es' if lang == 'Español' else 'en'


def install_sidebar_tools() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_ara_sidebar_safety_v12', False):
        return
    st._ara_sidebar_safety_v12 = True
    real_config = st.set_page_config
    real_md = st.markdown
    real_side_radio = st.sidebar.radio
    real_side_select = st.sidebar.selectbox
    real_dg_select = DeltaGenerator.selectbox
    real_dg_radio = getattr(DeltaGenerator, 'radio', None)

    def css() -> None:
        try:
            real_md(CSS, unsafe_allow_html=True)
        except Exception:
            pass

    def page_config(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault('initial_sidebar_state', 'collapsed')
        reset_sidebar_render_guard(st)
        out = real_config(*args, **kwargs)
        css()
        return out

    def after(value: object) -> object:
        render_curated_sidebar(st, sync_language(st, value))
        return value

    def radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_side_radio(label, options, *args, **kwargs)
        return after(value) if is_language_widget(label, options) else value

    def selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if not is_language_widget(label, options):
            return real_side_select(label, options, *args, **kwargs)
        opts = list(options)
        key = kwargs.get('key')
        current = normal_language(st.session_state.get(key or 'global_language', 'English'))
        value = real_side_radio('Idioma' if current == 'Español' else 'Language', opts, index=opts.index(current) if current in opts else 0, key=key, horizontal=True)
        return after(value)

    def dg_select(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_widget(label, options):
            return selectbox(label, options, *args, **kwargs)
        return real_dg_select(self, label, options, *args, **kwargs)

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_dg_radio(self, label, options, *args, **kwargs) if real_dg_radio else real_side_radio(label, options, *args, **kwargs)
        return after(value) if is_language_widget(label, options) else value

    st.set_page_config = page_config
    st.sidebar.radio = radio
    st.sidebar.selectbox = selectbox
    DeltaGenerator.selectbox = dg_select
    if real_dg_radio is not None:
        DeltaGenerator.radio = dg_radio
    css()

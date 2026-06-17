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
BRAND_RENDERED_KEY = '_aba_sidebar_brand_once_v23'
PAGES_RENDERED_KEY = '_aba_sidebar_pages_once_v23'
SIDEBAR_CALL_ACTIVE_KEY = '_aba_sidebar_language_active_v23'
CSS = '''
<style>
[data-testid="stSidebarNav"],section[data-testid="stSidebar"] [data-testid="stSidebarNav"],section[data-testid="stSidebar"] nav[aria-label="Page navigation"],section[data-testid="stSidebar"] nav[aria-label="pages"],section[data-testid="stSidebar"] nav[aria-label="Pages"]{display:none!important;height:0!important;max-height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;}
[data-testid="collapsedControl"]{z-index:999999!important;}
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"]:has(h3 span[style*="color"]),section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"]:has(h3 span[class*="green"]),section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"]:has(h3 span[class*="red"]){display:none!important;height:0!important;max-height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;}
section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"]:first-of-type{display:none!important;height:0!important;max-height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;}
section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"]:has(hr):first-of-type{display:none!important;height:0!important;max-height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;}
.aba-sidebar-brand{display:inline-block!important;font-size:1.66rem!important;line-height:1.18!important;font-weight:850!important;letter-spacing:-.02em!important;margin:.25rem 0 .55rem 0!important;text-shadow:0 1px 0 rgba(0,0,0,.72),0 2px 3px rgba(0,0,0,.45)!important;filter:none!important;}
.aba-brand-green{color:#00A85A!important;-webkit-text-fill-color:#00A85A!important;}
.aba-brand-white{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;}
.aba-brand-red{color:#FF3B3B!important;-webkit-text-fill-color:#FF3B3B!important;}
.aba-sidebar-tagline{color:rgba(250,250,250,.62)!important;font-size:1.02rem!important;margin:0 0 1.35rem 0!important;}
.aba-sidebar-brand ~ .aba-sidebar-brand,.aba-sidebar-tagline ~ .aba-sidebar-tagline{display:none!important;}
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


def _reset_current_sidebar_call(st: Any) -> None:
    try:
        st.session_state[BRAND_RENDERED_KEY] = False
        st.session_state[PAGES_RENDERED_KEY] = False
    except Exception:
        pass


def _already_rendered(st: Any, key: str) -> bool:
    try:
        if st.session_state.get(key):
            return True
        st.session_state[key] = True
    except Exception:
        pass
    return False


def render_sidebar_brand(st: Any) -> None:
    if _already_rendered(st, BRAND_RENDERED_KEY):
        return
    inject_sidebar_css(st)
    with st.sidebar:
        st.markdown('<div class="aba-sidebar-brand"><span class="aba-brand-green">ABA</span> <span class="aba-brand-white">Signal</span> <span class="aba-brand-red">Pro</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="aba-sidebar-tagline">{APP_TAGLINE}</div>', unsafe_allow_html=True)


def render_curated_sidebar(st: Any, language: object = 'English') -> None:
    if _already_rendered(st, PAGES_RENDERED_KEY):
        return
    lang = normal_language(language)
    with st.sidebar:
        st.divider()
        st.subheader('Herramientas' if lang == 'Español' else 'Tools')
        for en, es, path in PAGES:
            label = es if lang == 'Español' else en
            try:
                st.page_link(path, label=label)
            except Exception:
                st.caption(label)
        st.divider()


def sidebar_language_selector(st: Any, *, key: str, default: str = 'English') -> str:
    inject_sidebar_css(st)
    current = normal_language(st.session_state.get(key, st.session_state.get('global_language', default)))
    options = ['English', 'Español']
    selected = st.sidebar.radio('Idioma' if current == 'Español' else 'Language', options, index=options.index(current), key=key, horizontal=True)
    return 'es' if sync_language(st, selected) == 'Español' else 'en'


def install_sidebar_tools() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_sidebar_tools_installed_v23', False):
        return
    st._aba_sidebar_tools_installed_v23 = True
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
        out = real_config(*args, **kwargs)
        css()
        return out

    def begin_language_call() -> bool:
        try:
            if st.session_state.get(SIDEBAR_CALL_ACTIVE_KEY):
                return False
            st.session_state[SIDEBAR_CALL_ACTIVE_KEY] = True
            _reset_current_sidebar_call(st)
        except Exception:
            pass
        return True

    def end_language_call() -> None:
        try:
            st.session_state[SIDEBAR_CALL_ACTIVE_KEY] = False
        except Exception:
            pass

    def radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if not is_language_widget(label, options):
            return real_side_radio(label, options, *args, **kwargs)
        outer = begin_language_call()
        try:
            if outer:
                render_sidebar_brand(st)
            value = real_side_radio(label, options, *args, **kwargs)
            if outer:
                css()
                render_curated_sidebar(st, sync_language(st, value))
            return value
        finally:
            if outer:
                end_language_call()

    def selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if not is_language_widget(label, options):
            return real_side_select(label, options, *args, **kwargs)
        outer = begin_language_call()
        try:
            if outer:
                render_sidebar_brand(st)
            opts = list(options)
            key = kwargs.get('key')
            current = normal_language(st.session_state.get(key or 'global_language', 'English'))
            value = real_side_radio('Idioma' if current == 'Español' else 'Language', opts, index=opts.index(current) if current in opts else 0, key=key, horizontal=True)
            if outer:
                css()
                render_curated_sidebar(st, sync_language(st, value))
            return value
        finally:
            if outer:
                end_language_call()

    def dg_select(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_widget(label, options):
            return selectbox(label, options, *args, **kwargs)
        return real_dg_select(self, label, options, *args, **kwargs)

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if not is_language_widget(label, options):
            return real_dg_radio(self, label, options, *args, **kwargs) if real_dg_radio else real_side_radio(label, options, *args, **kwargs)
        outer = begin_language_call()
        try:
            if outer:
                render_sidebar_brand(st)
            value = real_dg_radio(self, label, options, *args, **kwargs) if real_dg_radio else real_side_radio(label, options, *args, **kwargs)
            if outer:
                css()
                render_curated_sidebar(st, sync_language(st, value))
            return value
        finally:
            if outer:
                end_language_call()

    st.set_page_config = page_config
    st.sidebar.radio = radio
    st.sidebar.selectbox = selectbox
    DeltaGenerator.selectbox = dg_select
    if real_dg_radio is not None:
        DeltaGenerator.radio = dg_radio
    css()

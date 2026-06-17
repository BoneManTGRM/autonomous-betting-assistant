from __future__ import annotations

from typing import Any

APP_NAME = 'ABA Signal Pro'
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
BRIGHT_GOLD = '#FFD54A'
CSS = f'''
<style>
[data-testid="stSidebarNav"],section[data-testid="stSidebar"] [data-testid="stSidebarNav"],section[data-testid="stSidebar"] nav[aria-label="Page navigation"],section[data-testid="stSidebar"] nav[aria-label="pages"],section[data-testid="stSidebar"] nav[aria-label="Pages"]{{display:none!important;height:0!important;max-height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;}}
[data-testid="collapsedControl"]{{z-index:999999!important;}}
.aba-sidebar-brand{{color:{BRIGHT_GOLD}!important;-webkit-text-fill-color:{BRIGHT_GOLD}!important;font-size:1.66rem!important;line-height:1.18!important;font-weight:850!important;letter-spacing:-.02em!important;text-shadow:0 0 14px rgba(255,213,74,.38)!important;margin:.25rem 0 .55rem 0!important;}}
.aba-sidebar-tagline{{color:rgba(250,250,250,.62)!important;font-size:1.02rem!important;margin:0 0 1.35rem 0!important;}}
section[data-testid="stSidebar"] h3:has(span[style*="color"]),section[data-testid="stSidebar"] h3:has(span[style*="color"]) *,section[data-testid="stSidebar"] h3:has(span[class*="green"]),section[data-testid="stSidebar"] h3:has(span[class*="green"]) *,section[data-testid="stSidebar"] h3:has(span[class*="red"]),section[data-testid="stSidebar"] h3:has(span[class*="red"]) *{{color:{BRIGHT_GOLD}!important;-webkit-text-fill-color:{BRIGHT_GOLD}!important;font-size:1.16em!important;line-height:1.18!important;font-weight:800!important;text-shadow:0 0 14px rgba(255,213,74,.38)!important;}}
@media(max-width:900px){{section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{{padding:.75rem .9rem!important;overflow-x:hidden!important}}.block-container{{padding-left:.85rem!important;padding-right:.85rem!important;max-width:100vw!important}}}}
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


def render_sidebar_brand(st: Any) -> None:
    inject_sidebar_css(st)
    with st.sidebar:
        st.markdown(f'<div class="aba-sidebar-brand">{APP_NAME}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="aba-sidebar-tagline">{APP_TAGLINE}</div>', unsafe_allow_html=True)


def render_curated_sidebar(st: Any, language: object = 'English') -> None:
    """Render only the curated page links below the language selector."""
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
    lang = sync_language(st, selected)
    return 'es' if lang == 'Español' else 'en'


def install_sidebar_tools() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_ara_sidebar_safety_v17', False):
        return
    st._ara_sidebar_safety_v17 = True
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

    def after(value: object) -> object:
        css()
        render_curated_sidebar(st, sync_language(st, value))
        return value

    def radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_widget(label, options):
            render_sidebar_brand(st)
            value = real_side_radio(label, options, *args, **kwargs)
            return after(value)
        return real_side_radio(label, options, *args, **kwargs)

    def selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if not is_language_widget(label, options):
            return real_side_select(label, options, *args, **kwargs)
        render_sidebar_brand(st)
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
        if is_language_widget(label, options):
            render_sidebar_brand(st)
            value = real_dg_radio(self, label, options, *args, **kwargs) if real_dg_radio else real_side_radio(label, options, *args, **kwargs)
            return after(value)
        return real_dg_radio(self, label, options, *args, **kwargs) if real_dg_radio else real_side_radio(label, options, *args, **kwargs)

    st.set_page_config = page_config
    st.sidebar.radio = radio
    st.sidebar.selectbox = selectbox
    DeltaGenerator.selectbox = dg_select
    if real_dg_radio is not None:
        DeltaGenerator.radio = dg_radio
    css()

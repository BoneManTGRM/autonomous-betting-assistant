from __future__ import annotations

from typing import Any

PAGES = (
    ('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor.py'),
    ('Ultra 70 Profit Mode', 'Ultra 70 Profit Mode', 'pages/ultra80_profit_mode.py'),
    ('Simulation Lab', 'Laboratorio de Simulación', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'Optimizador de Umbrales', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'Cuotas y Valor', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'Odds Lock Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'Dashboard Público', 'pages/public_proof_dashboard.py'),
    ('Reset Lock File', 'Reiniciar Archivo', 'pages/reset_lock_file.py'),
    ('Learning Memory', 'Memoria', 'pages/learn_memory.py'),
)
KEYS = ('global_language', 'pro_predictor_language', 'odds_lock_pro_language', 'public_proof_dashboard_language', 'learn_memory_language')
CSS = '<style>@media(max-width:900px){section[data-testid="stSidebar"]{width:min(86vw,360px)!important;min-width:min(86vw,360px)!important;max-width:min(86vw,360px)!important}.block-container{padding-left:.85rem!important;padding-right:.85rem!important}}</style>'


def lang(value: object) -> str:
    s = str(value or '').lower()
    return 'Español' if s.startswith('es') or 'español' in s or 'espanol' in s else 'English'


def is_language(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    return 'English' in opts and 'Español' in opts and 'language' in str(label or '').lower()


def sync(st: Any, value: object) -> str:
    l = lang(value)
    for k in KEYS:
        try:
            st.session_state[k] = l
        except Exception:
            pass
    return l


def brand(st: Any) -> None:
    if st.session_state.get('_aba_sidebar_brand_fixed'):
        return
    st.session_state['_aba_sidebar_brand_fixed'] = True
    with st.sidebar:
        st.markdown('### :green[ABA] Signal :red[Pro]')
        st.caption('Powered by Reparodynamics')
        st.markdown('---')


def nav(st: Any, value: object) -> None:
    if st.session_state.get('_aba_sidebar_pages_fixed'):
        return
    st.session_state['_aba_sidebar_pages_fixed'] = True
    l = lang(value)
    with st.sidebar:
        st.markdown('### Herramientas' if l == 'Español' else '### Pages')
        for en, es, path in PAGES:
            try:
                st.page_link(path, label=es if l == 'Español' else en)
            except Exception:
                st.caption(es if l == 'Español' else en)
        st.markdown('---')
        st.markdown('### Flujo' if l == 'Español' else '### Workflow')
        notes = ('Predictor Pro → Máxima Confianza → Odds Lock Pro → Dashboard Público → Memoria.', 'Picks bloqueados y ROI viven en Odds Lock Pro / Dashboard Público.') if l == 'Español' else ('Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory.', 'Locked picks and ROI live in Odds Lock Pro / Public Proof Dashboard.')
        for note in notes:
            st.caption(note)


def install_sidebar_tools() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_sidebar_tools_fixed_v1', False):
        return
    st._aba_sidebar_tools_fixed_v1 = True
    old_config = st.set_page_config
    old_markdown = st.markdown
    old_radio = getattr(DeltaGenerator, 'radio', None)
    old_select = DeltaGenerator.selectbox

    def config(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault('initial_sidebar_state', 'expanded')
        out = old_config(*args, **kwargs)
        try:
            old_markdown(CSS, unsafe_allow_html=True)
            brand(st)
        except Exception:
            pass
        return out

    def radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language(label, options):
            brand(st)
            value = old_radio(self, label, options, *args, **kwargs) if old_radio is not None else st.radio(label, options, *args, **kwargs)
            nav(st, sync(st, value))
            return value
        return old_radio(self, label, options, *args, **kwargs) if old_radio is not None else st.radio(label, options, *args, **kwargs)

    def select(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language(label, options):
            brand(st)
            value = old_select(self, label, options, *args, **kwargs)
            nav(st, sync(st, value))
            return value
        return old_select(self, label, options, *args, **kwargs)

    st.set_page_config = config
    if old_radio is not None:
        DeltaGenerator.radio = radio
    DeltaGenerator.selectbox = select

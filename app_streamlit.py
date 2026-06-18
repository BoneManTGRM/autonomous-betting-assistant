from __future__ import annotations

from typing import Any

import streamlit as st

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
APP_BUILD = 'clean-shell-sidebar-v8'
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
PAGE_LINKS = [
    ('Signal Board', 'pages/signal_board.py'),
    ('Pro Predictor', 'pages/pro_predictor.py'),
    ('Simulation Lab', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'pages/learn_memory.py'),
]
REGISTERED_PAGES = PAGE_LINKS + [('Reset Lock File', 'pages/reset_lock_file.py')]

st.set_page_config(page_title=APP_NAME, layout='wide', initial_sidebar_state='expanded')


def _is_numeric_value(value: Any) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def _slider_as_number_input(target: Any, original_slider: Any, *args: Any, **kwargs: Any) -> Any:
    original_kwargs = dict(kwargs)
    try:
        if args:
            label = args[0]
            rest = list(args[1:])
        else:
            label = kwargs.pop('label')
            rest = []
        ordered = [
            'min_value', 'max_value', 'value', 'step', 'format', 'key', 'help',
            'on_change', 'args', 'kwargs', 'disabled', 'label_visibility',
        ]
        params: dict[str, Any] = {}
        for name in ordered:
            if rest:
                params[name] = rest.pop(0)
            elif name in kwargs:
                params[name] = kwargs.pop(name)
        if rest:
            return original_slider(*args, **original_kwargs)
        min_value = params.get('min_value')
        max_value = params.get('max_value')
        value = params.get('value')
        step = params.get('step')
        if isinstance(value, (list, tuple)) or not all(_is_numeric_value(item) for item in (min_value, max_value, value, step)):
            return original_slider(*args, **original_kwargs)
        if value is None:
            value = min_value if min_value is not None else 0.0
        number_kwargs: dict[str, Any] = dict(kwargs)
        for name in ('min_value', 'max_value', 'step', 'format', 'key', 'help', 'on_change', 'args', 'kwargs'):
            if name in params and params[name] is not None:
                number_kwargs[name] = params[name]
        if 'disabled' in params:
            number_kwargs['disabled'] = params['disabled']
        if 'label_visibility' in params:
            number_kwargs['label_visibility'] = params['label_visibility']
        number_kwargs['value'] = value
        return target.number_input(label, **number_kwargs)
    except Exception:
        return original_slider(*args, **original_kwargs)


if not getattr(st, '_aba_numeric_slider_patch', False):
    st._aba_original_slider = st.slider

    def _st_slider_as_number_input(*args: Any, **kwargs: Any) -> Any:
        return _slider_as_number_input(st, st._aba_original_slider, *args, **kwargs)

    st.slider = _st_slider_as_number_input
    st._aba_numeric_slider_patch = True

try:
    from streamlit.delta_generator import DeltaGenerator

    if not getattr(DeltaGenerator, '_aba_numeric_slider_patch', False):
        DeltaGenerator._aba_original_slider = DeltaGenerator.slider

        def _delta_slider_as_number_input(self: Any, *args: Any, **kwargs: Any) -> Any:
            return _slider_as_number_input(self, DeltaGenerator._aba_original_slider.__get__(self, DeltaGenerator), *args, **kwargs)

        DeltaGenerator.slider = _delta_slider_as_number_input
        DeltaGenerator._aba_numeric_slider_patch = True
except Exception:
    pass


def _current_language() -> str:
    for key in LANGUAGE_KEYS:
        value = st.session_state.get(key)
        if value in ('English', 'Español'):
            return value
    return 'English'


def _sync_language(value: str) -> None:
    if value not in ('English', 'Español'):
        value = 'English'
    for key in LANGUAGE_KEYS:
        st.session_state[key] = value


def _is_language_widget(label: Any, options: Any) -> bool:
    try:
        values = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return 'English' in values and 'Español' in values and ('language' in text or 'idioma' in text)


def _nav_label(label: str, language: str) -> str:
    if language != 'Español':
        return label
    translations = {
        'Pro Predictor': 'Predictor Pro',
        'Simulation Lab': 'Laboratorio de Simulación',
        'Threshold Optimizer': 'Optimizador de Umbral',
        'Public Proof Dashboard': 'Dashboard Público de Prueba',
        'Learning Memory': 'Memoria de Aprendizaje',
    }
    return translations.get(label, label)


with st.sidebar:
    st.markdown('### :green[ABA] Signal :red[Pro]')
    st.caption(APP_TAGLINE)
    st.markdown('---')
    _language = st.radio('Language', ['English', 'Español'], index=1 if _current_language() == 'Español' else 0, key='global_language', horizontal=True)
    _sync_language(_language)
    st.markdown('---')
    st.markdown('### ' + ('Herramientas' if _language == 'Español' else 'Tools'))
    for _label, _path in PAGE_LINKS:
        try:
            st.page_link(_path, label=_nav_label(_label, _language))
        except Exception:
            st.caption(_nav_label(_label, _language))


_real_sidebar_radio = st.sidebar.radio
_real_sidebar_selectbox = st.sidebar.selectbox


def _hidden_language_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_language_widget(label, options):
        key = kwargs.get('key')
        if key:
            st.session_state[key] = st.session_state.get('global_language', 'English')
        return st.session_state.get('global_language', 'English')
    return _real_sidebar_radio(label, options, *args, **kwargs)


def _hidden_language_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_language_widget(label, options):
        key = kwargs.get('key')
        if key:
            st.session_state[key] = st.session_state.get('global_language', 'English')
        return st.session_state.get('global_language', 'English')
    return _real_sidebar_selectbox(label, options, *args, **kwargs)


st.sidebar.radio = _hidden_language_radio
st.sidebar.selectbox = _hidden_language_selectbox

PAGES = [st.Page(path, title=label) for label, path in REGISTERED_PAGES]
current_page = st.navigation(PAGES, position='hidden')
st.set_page_config = lambda *args, **kwargs: None
current_page.run()

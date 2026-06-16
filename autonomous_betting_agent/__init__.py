from __future__ import annotations

from typing import Any

from .learning import GradedPrediction, ProbabilityCalibrator, fit_probability_calibrator, parse_graded_csv
from .models import EventResearchInput, PredictionResult, TeamSnapshot
from .researcher import AutonomousBettingAgent
from .tgrm import TGRMLoop
from .tracking import PredictionLedgerRow, SelectionDecision, SelectionPolicy, TrackingReport, choose_decision, summarize_tracking

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'


def _install_streamlit_helpers() -> None:
    try:
        import pandas as pd
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    if getattr(st, '_aba_streamlit_helpers_v7_installed', False):
        return
    st._aba_streamlit_helpers_v7_installed = True

    real_set_page_config = st.set_page_config
    real_st_selectbox = st.selectbox
    real_dg_selectbox = DeltaGenerator.selectbox
    real_st_dataframe = st.dataframe
    real_dg_dataframe = DeltaGenerator.dataframe

    language_keys = [
        'global_language', 'app_language', 'scanner_pro_language', 'pro_predictor_language',
        'what_are_the_odds_language', 'odds_lock_pro_language', 'public_proof_dashboard_language',
        'auto_result_grading_language', 'learning_memory_language', 'learn_memory_language',
    ]

    tools = (
        ('Scanner Pro', 'Scanner Pro', 'pages/scanner_pro.py'),
        (APP_NAME, APP_NAME, 'pages/pro_predictor.py'),
        ('What Are the Odds', 'Cuotas y Valor', 'pages/what_are_the_odds.py'),
        ('Odds Lock Pro', 'Odds Lock Pro', 'pages/odds_lock_pro.py'),
        ('Public Proof Dashboard', 'Dashboard Publico', 'pages/public_proof_dashboard.py'),
        ('Learning Memory', 'Learning Memory', 'pages/learn_memory.py'),
    )

    def normalize_language(value: object) -> str:
        text = str(value or '').strip().lower()
        if text.startswith('es') or 'español' in text or 'espanol' in text:
            return 'Español'
        if text.startswith('en') or 'english' in text:
            return 'English'
        return ''

    def current_language() -> str:
        for key in language_keys:
            value = normalize_language(st.session_state.get(key))
            if value:
                return value
        return 'Español'

    def save_language(value: object) -> str:
        selected = normalize_language(value) or current_language()
        for key in language_keys:
            try:
                st.session_state[key] = selected
            except Exception:
                pass
        return selected

    def render_nav(lang: str) -> None:
        with st.sidebar:
            st.markdown('### :green[ABA] Signal :red[Pro]')
            st.caption(APP_TAGLINE)
            st.markdown('---')
            st.markdown('### Herramientas' if lang == 'Español' else '### Tools')
            for english, spanish, path in tools:
                label = spanish if lang == 'Español' else english
                try:
                    st.page_link(path, label=label)
                except Exception:
                    st.caption(label)

    def patched_set_page_config(*args: Any, **kwargs: Any) -> Any:
        if not args:
            kwargs.setdefault('page_title', APP_NAME)
            kwargs.setdefault('initial_sidebar_state', 'expanded')
        return real_set_page_config(*args, **kwargs)

    def language_selectbox(label: Any, options: Any, args: tuple[Any, ...], kwargs: dict[str, Any], original: Any, target: Any = None) -> Any:
        try:
            opts = list(options)
        except Exception:
            opts = []
        label_text = str(label or '').lower()
        is_language = ('language' in label_text or 'idioma' in label_text) and 'English' in opts and 'Español' in opts
        if not is_language:
            if target is None:
                return original(label, options, *args, **kwargs)
            return original(target, label, options, *args, **kwargs)
        kwargs = dict(kwargs)
        key = kwargs.get('key') or 'global_language'
        kwargs['key'] = key
        current = normalize_language(st.session_state.get(key)) or current_language()
        kwargs['index'] = opts.index(current) if current in opts else 0
        display_label = 'Idioma' if current == 'Español' else 'Language'
        if target is None:
            value = original(display_label, opts, *args, **kwargs)
        else:
            value = original(target, display_label, opts, *args, **kwargs)
        selected = save_language(value)
        render_nav(selected)
        return selected

    def patched_st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return language_selectbox(label, options, args, kwargs, real_st_selectbox)

    def patched_dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return language_selectbox(label, options, args, kwargs, real_dg_selectbox, target=self)

    def patched_st_dataframe(data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_st_dataframe(data, *args, **kwargs)

    def patched_dg_dataframe(self: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_dg_dataframe(self, data, *args, **kwargs)

    st.set_page_config = patched_set_page_config
    st.selectbox = patched_st_selectbox
    DeltaGenerator.selectbox = patched_dg_selectbox
    st.dataframe = patched_st_dataframe
    DeltaGenerator.dataframe = patched_dg_dataframe


_install_streamlit_helpers()

__all__ = [
    'AutonomousBettingAgent', 'EventResearchInput', 'GradedPrediction', 'PredictionLedgerRow',
    'PredictionResult', 'ProbabilityCalibrator', 'SelectionDecision', 'SelectionPolicy',
    'TeamSnapshot', 'TGRMLoop', 'TrackingReport', 'choose_decision', 'fit_probability_calibrator',
    'parse_graded_csv', 'summarize_tracking',
]

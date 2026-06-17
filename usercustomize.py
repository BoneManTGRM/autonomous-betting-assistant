from __future__ import annotations

from typing import Any

try:
    from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer
    install_odds_breakdown_normalizer()
except Exception:
    pass

try:
    from autonomous_betting_agent.local_users import install_streamlit_local_user_selector
    install_streamlit_local_user_selector()
except Exception:
    pass

LANGUAGE_KEYS = (
    'global_language', 'app_language', 'pro_predictor_language', 'ultra80_profit_mode_language',
    'simulation_lab_language', 'what_are_the_odds_language', 'odds_lock_pro_language',
    'public_proof_dashboard_language', 'reset_lock_file_language', 'learn_memory_language',
    'learning_memory_language', 'threshold_optimizer_language',
)

TOOLS_EN = (
    'Pro Predictor', 'Ultra 70 Profit Mode', 'Simulation Lab', 'Threshold Optimizer',
    'What Are the Odds', 'Odds Lock Pro', 'Public Proof Dashboard', 'Reset Lock File', 'Learning Memory',
)
TOOLS_ES = (
    'Predictor Pro', 'Ultra 70 Profit Mode', 'Laboratorio de Simulación', 'Optimizador de Umbrales',
    'Cuotas y Valor', 'Bloqueo de Cuotas Pro', 'Dashboard Público de Prueba', 'Reiniciar Archivo de Bloqueo', 'Memoria de Aprendizaje',
)


def _normal_language(value: object) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'Español'
    return 'English'


def _sync_language(st: Any, value: object) -> str:
    normalized = _normal_language(value)
    for key in LANGUAGE_KEYS:
        try:
            st.session_state[key] = normalized
        except Exception:
            pass
    return normalized


def _is_language_widget(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return ('language' in text or 'idioma' in text) and 'English' in opts and 'Español' in opts


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return (
        value.replace('Scanner Pro', 'Pro Predictor')
        .replace('scanner strength', 'signal strength')
        .replace('Scanner strength', 'Signal strength')
        .replace('escáner', 'señal')
        .replace('Escáner', 'Señal')
    )


def _render_clean_sidebar(st: Any, language: object) -> None:
    lang = _normal_language(language)
    key = '_aba_clean_sidebar_plain_rendered_v1'
    if st.session_state.get(key):
        return
    st.session_state[key] = True
    if lang == 'Español':
        tools_title = 'Herramientas'
        workflow_title = 'Flujo'
        tools = TOOLS_ES
        workflow = 'Predictor Pro → Máxima Confianza → Odds Lock Pro → Dashboard Público → Memoria.'
    else:
        tools_title = 'Tools'
        workflow_title = 'Workflow'
        tools = TOOLS_EN
        workflow = 'Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory.'
    with st.sidebar:
        st.markdown('### :green[ABA] Signal :red[Pro]')
        st.caption('Powered by Reparodynamics')
        st.markdown('---')
        st.markdown(f'### {tools_title}')
        for tool in tools:
            st.caption(tool)
        st.markdown('---')
        st.markdown(f'### {workflow_title}')
        st.caption(workflow)


def _install_clean_sidebar_patch() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_clean_sidebar_plain_installed_v1', False):
        return
    st._aba_clean_sidebar_plain_installed_v1 = True

    real_st_radio = st.radio
    real_dg_radio = getattr(DeltaGenerator, 'radio', None)
    real_st_selectbox = st.selectbox
    real_dg_selectbox = DeltaGenerator.selectbox
    real_caption = st.caption
    real_markdown = st.markdown
    real_info = st.info
    real_write = st.write
    real_dg_caption = DeltaGenerator.caption
    real_dg_markdown = DeltaGenerator.markdown
    real_dg_info = DeltaGenerator.info
    real_dg_write = DeltaGenerator.write

    def st_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_st_radio(label, options, *args, **kwargs)
        if _is_language_widget(label, options):
            _render_clean_sidebar(st, _sync_language(st, value))
        return value

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_dg_radio(self, label, options, *args, **kwargs) if real_dg_radio is not None else real_st_radio(label, options, *args, **kwargs)
        if _is_language_widget(label, options):
            _render_clean_sidebar(st, _sync_language(st, value))
        return value

    def st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_st_selectbox(label, options, *args, **kwargs)
        if _is_language_widget(label, options):
            _render_clean_sidebar(st, _sync_language(st, value))
        return value

    def dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_dg_selectbox(self, label, options, *args, **kwargs)
        if _is_language_widget(label, options):
            _render_clean_sidebar(st, _sync_language(st, value))
        return value

    st.radio = st_radio
    st.selectbox = st_selectbox
    DeltaGenerator.selectbox = dg_selectbox
    if real_dg_radio is not None:
        DeltaGenerator.radio = dg_radio
    st.caption = lambda body, *a, **k: real_caption(_clean_text(body), *a, **k)
    st.markdown = lambda body, *a, **k: real_markdown(_clean_text(body), *a, **k)
    st.info = lambda body, *a, **k: real_info(_clean_text(body), *a, **k)
    st.write = lambda *a, **k: real_write(*[_clean_text(x) for x in a], **k)
    DeltaGenerator.caption = lambda self, body, *a, **k: real_dg_caption(self, _clean_text(body), *a, **k)
    DeltaGenerator.markdown = lambda self, body, *a, **k: real_dg_markdown(self, _clean_text(body), *a, **k)
    DeltaGenerator.info = lambda self, body, *a, **k: real_dg_info(self, _clean_text(body), *a, **k)
    DeltaGenerator.write = lambda self, *a, **k: real_dg_write(self, *[_clean_text(x) for x in a], **k)


_install_clean_sidebar_patch()

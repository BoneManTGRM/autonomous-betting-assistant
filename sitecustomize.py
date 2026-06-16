from __future__ import annotations

import builtins
import inspect
import os
from typing import Any

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'

NAV_TOOLS: tuple[tuple[str, str, str], ...] = (
    ('Scanner Pro', 'Scanner Pro', 'pages/scanner_pro.py'),
    (APP_NAME, 'ABA Signal Pro', 'pages/pro_predictor.py'),
    ('Ultra 70 Profit Mode', 'Ultra 70 Profit Mode', 'pages/ultra80_profit_mode.py'),
    ('Simulation Lab', 'Laboratorio de Simulación', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'Optimizador de Umbrales', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'Cuotas y Valor', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'Bloqueo de Cuotas Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'Dashboard Público de Prueba', 'pages/public_proof_dashboard.py'),
    ('Reset Lock File', 'Reiniciar Archivo de Bloqueo', 'pages/reset_lock_file.py'),
    ('Learning Memory', 'Memoria de Aprendizaje', 'pages/learn_memory.py'),
)

NAV_NOTES_EN = (
    'Workflow: Scanner Pro → ABA Signal Pro → Ultra 70 Profit Mode → Odds Lock Pro → Public Proof Dashboard → Threshold Optimizer → Learning Memory.',
    'Use Ultra 70 to send 70%+ lockable rows to Odds Lock Pro, while strict 80 proof remains tracked separately.',
    'Use Reset Lock File to clear one test-window proof ledger without touching other windows.',
)
NAV_NOTES_ES = (
    'Flujo: Scanner Pro → ABA Signal Pro → Ultra 70 Profit Mode → Bloqueo de Cuotas Pro → Dashboard Público de Prueba → Optimizador de Umbrales → Memoria de Aprendizaje.',
    'Usa Ultra 70 para enviar filas bloqueables 70%+ a Odds Lock Pro, manteniendo la prueba estricta 80 separada.',
    'Usa Reiniciar Archivo de Bloqueo para borrar el ledger de una ventana de prueba sin tocar las demás.',
)


def get_secret(*names: str) -> str:
    """Read a Streamlit secret or environment variable by one of several names."""
    try:
        import streamlit as st
    except Exception:
        st = None  # type: ignore[assignment]
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, '')).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret

try:
    import autonomous_betting_agent  # noqa: F401
except Exception:
    pass


def _normal_language(value: object) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'Español'
    if text.startswith('en') or 'english' in text:
        return 'English'
    return 'English'


def _sidebar_language() -> str:
    try:
        import streamlit as st
        for key in (
            'global_language', 'app_language', 'simulation_lab_language', 'pro_predictor_language',
            'ultra80_profit_mode_language', 'odds_lock_pro_language', 'public_proof_dashboard_language',
            'reset_lock_file_language', 'learn_memory_language', 'learning_memory_language',
            'threshold_optimizer_language', 'what_are_the_odds_language',
        ):
            value = st.session_state.get(key)
            if value:
                return _normal_language(value)
    except Exception:
        pass
    return 'English'


def _install_sidebar_nav_fallback() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_sidebar_nav_fallback_installed_v4', False):
        return
    st._aba_sidebar_nav_fallback_installed_v4 = True
    real_st_selectbox = st.selectbox
    real_dg_selectbox = DeltaGenerator.selectbox
    real_set_page_config = st.set_page_config

    def render_brand_once() -> None:
        if st.session_state.get('_aba_sidebar_brand_rendered_v4'):
            return
        st.session_state['_aba_sidebar_brand_rendered_v4'] = True
        with st.sidebar:
            st.markdown('### :green[ABA] Signal :red[Pro]')
            st.caption(APP_TAGLINE)
            st.markdown('---')

    def render_nav(lang: str | None = None) -> None:
        render_brand_once()
        lang = lang or _sidebar_language()
        with st.sidebar:
            st.markdown('### Herramientas' if lang == 'Español' else '### Tools')
            for english, spanish, path in NAV_TOOLS:
                label = spanish if lang == 'Español' else english
                try:
                    st.page_link(path, label=label)
                except Exception:
                    st.caption(label)
            st.markdown('---')
            st.markdown('### Flujo' if lang == 'Español' else '### Workflow')
            for note in (NAV_NOTES_ES if lang == 'Español' else NAV_NOTES_EN):
                st.caption(note)

    def is_language_selector(label: Any, options: Any) -> bool:
        try:
            opts = list(options)
        except Exception:
            return False
        label_text = str(label or '').lower()
        return ('language' in label_text or 'idioma' in label_text) and 'English' in opts and 'Español' in opts

    def patched_set_page_config(*args: Any, **kwargs: Any) -> Any:
        if not args:
            kwargs.setdefault('page_title', APP_NAME)
            kwargs.setdefault('initial_sidebar_state', 'expanded')
        result = real_set_page_config(*args, **kwargs)
        try:
            render_brand_once()
        except Exception:
            pass
        return result

    def patched_st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_selector(label, options):
            try:
                render_brand_once()
            except Exception:
                pass
        value = real_st_selectbox(label, options, *args, **kwargs)
        if is_language_selector(label, options):
            try:
                render_nav(_normal_language(value))
            except Exception:
                pass
        return value

    def patched_dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if is_language_selector(label, options):
            try:
                render_brand_once()
            except Exception:
                pass
        value = real_dg_selectbox(self, label, options, *args, **kwargs)
        if is_language_selector(label, options):
            try:
                render_nav(_normal_language(value))
            except Exception:
                pass
        return value

    st.set_page_config = patched_set_page_config
    st.selectbox = patched_st_selectbox
    DeltaGenerator.selectbox = patched_dg_selectbox


_install_sidebar_nav_fallback()

try:
    from autonomous_betting_agent.audit import enrich_prediction_frame, install_live_api_audit_context
    from autonomous_betting_agent.live_api_context import LiveAPIContextBuilder
    from autonomous_betting_agent.mobile_report import render_mobile_predictor_report

    install_live_api_audit_context(LiveAPIContextBuilder)
except Exception:
    enrich_prediction_frame = None  # type: ignore[assignment]
    render_mobile_predictor_report = None  # type: ignore[assignment]


def _called_from_page(page_name: str) -> bool:
    try:
        suffix = f'pages/{page_name}'.replace('\\', '/')
        return any(str(frame.filename).replace('\\', '/').endswith(suffix) for frame in inspect.stack())
    except Exception:
        return False


def _called_from_pro_predictor() -> bool:
    return _called_from_page('pro_predictor.py')


def _called_from_learning_memory() -> bool:
    return _called_from_page('learn_memory.py')


def _looks_like_predictor_report(data: Any) -> bool:
    try:
        import pandas as pd
    except Exception:
        return False
    if not isinstance(data, pd.DataFrame) or data.empty:
        return False
    keys = {str(col).strip().lower().replace(' ', '_') for col in data.columns}
    return bool(
        {'event', 'prediction', 'best_price'}.issubset(keys)
        or {'evento', 'pronostico', 'mejor_cuota'}.issubset(keys)
        or 'target_70_mode' in keys
        or 'modo_objetivo_70' in keys
    )


def _report_signature(data: Any) -> str:
    try:
        columns = ','.join(str(col) for col in data.columns[:12])
        return f'{len(data)}:{columns}:{str(data.head(1).to_dict())[:160]}'
    except Exception:
        return 'unknown'


def _install_page_helpers() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_page_helpers_installed', False):
        return
    st._aba_page_helpers_installed = True
    real_st_dataframe = st.dataframe
    real_dg_dataframe = DeltaGenerator.dataframe
    real_subheader = st.subheader

    def capture(data: Any) -> Any:
        if _called_from_pro_predictor() and _looks_like_predictor_report(data):
            try:
                captured = data.copy()
                if enrich_prediction_frame is not None:
                    captured = enrich_prediction_frame(captured)
                st.session_state['_aba_pro_predictor_latest_report'] = captured
                return captured
            except Exception:
                pass
        return data

    def should_render_mobile(data: Any) -> bool:
        if not (_called_from_pro_predictor() and _looks_like_predictor_report(data)):
            return False
        signature = _report_signature(data)
        rendered = st.session_state.setdefault('_aba_mobile_report_signatures', set())
        if signature in rendered:
            return False
        rendered.add(signature)
        return True

    def patched_st_dataframe(data: Any = None, *args: Any, **kwargs: Any) -> Any:
        captured = capture(data)
        if render_mobile_predictor_report is not None and should_render_mobile(captured):
            return render_mobile_predictor_report(captured, table_renderer=real_st_dataframe)
        return real_st_dataframe(data, *args, **kwargs)

    def patched_dg_dataframe(self: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        capture(data)
        return real_dg_dataframe(self, data, *args, **kwargs)

    def render_learning_reader_once() -> None:
        if st.session_state.get('_aba_learning_report_reader_rendered'):
            return
        st.session_state['_aba_learning_report_reader_rendered'] = True
        try:
            from autonomous_betting_agent.learning_report_reader import render_learning_report_reader

            render_learning_report_reader()
        except Exception as exc:
            real_subheader(f'Odds report reader could not load: {exc}')

    def patched_subheader(body: Any, *args: Any, **kwargs: Any) -> Any:
        result = real_subheader(body, *args, **kwargs)
        text = str(body)
        if _called_from_learning_memory() and ('Train from finished games' in text or 'Entrenar con partidos terminados' in text):
            render_learning_reader_once()
        return result

    st.dataframe = patched_st_dataframe
    DeltaGenerator.dataframe = patched_dg_dataframe
    st.subheader = patched_subheader


_install_page_helpers()

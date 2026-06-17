from __future__ import annotations

import builtins
import inspect
import os
from typing import Any

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
PREDICTOR_TOOL_NAME = 'Pro Predictor'

NAV_TOOLS: tuple[tuple[str, str, str], ...] = (
    ('Scanner Pro', 'Scanner Pro', 'pages/scanner_pro.py'),
    (PREDICTOR_TOOL_NAME, PREDICTOR_TOOL_NAME, 'pages/pro_predictor.py'),
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
    'Workflow: Scanner Pro → Pro Predictor → Ultra 70 Profit Mode → Odds Lock Pro → Public Proof Dashboard → Threshold Optimizer → Learning Memory.',
    'Use Ultra 70 to send 70%+ lockable rows to Odds Lock Pro, while strict 80 proof remains tracked separately.',
    'Use Reset Lock File to clear one test-window proof ledger without touching other windows.',
)
NAV_NOTES_ES = (
    'Flujo: Scanner Pro → Pro Predictor → Ultra 70 Profit Mode → Bloqueo de Cuotas Pro → Dashboard Público de Prueba → Optimizador de Umbrales → Memoria de Aprendizaje.',
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


def _is_tennis_text(*values: Any) -> bool:
    text = ' '.join(str(value or '').lower().replace('_', ' ').replace('-', ' ') for value in values)
    return any(token in text for token in ('tennis', ' atp', ' wta', 'tennis atp', 'tennis wta'))


def _install_tennis_sportsdataio_skip() -> None:
    """Treat tennis as SportsDataIO-not-applicable while preserving odds scans.

    SportsDataIO enrichment is useful for team sports in this app. Tennis should keep Odds API
    odds/probability data, but it should not be marked as failed SportsDataIO coverage.
    """
    try:
        builder = LiveAPIContextBuilder  # type: ignore[name-defined]
    except Exception:
        return
    if getattr(builder, '_aba_tennis_sdio_skip_installed_v1', False):
        return
    original = builder.context_for_event

    def patched_context_for_event(self: Any, event: Any, *, pick_name: str) -> dict[str, Any]:
        context = original(self, event, pick_name=pick_name)
        sport_key = getattr(event, 'sport_key', '')
        sport_title = getattr(event, 'sport_title', '')
        if _is_tennis_text(sport_key, sport_title):
            context.update(
                {
                    'sportsdataio_source_used': 'yes',
                    'sportsdataio_status': 'skipped_not_applicable_for_tennis',
                    'sportsdataio_sport': 'tennis_not_applicable',
                    'sportsdataio_team_metadata_used': 'not_applicable',
                    'sportsdataio_home_team_matched': 'not_applicable',
                    'sportsdataio_away_team_matched': 'not_applicable',
                    'sportsdataio_injuries_status': 'skipped_not_applicable_for_tennis',
                    'sportsdataio_picked_team_injury_count': 0,
                    'stats_source_reason': 'SportsDataIO skipped: tennis uses odds-only context in this workflow.',
                    'injury_source_reason': 'SportsDataIO injuries skipped: tennis is not a supported enrichment target in this workflow.',
                }
            )
        return context

    builder.context_for_event = patched_context_for_event
    builder._aba_tennis_sdio_skip_installed_v1 = True


_install_tennis_sportsdataio_skip()


def _called_from_page(page_name: str) -> bool:
    try:
        suffix = f'pages/{page_name}'.replace('\\', '/')
        return any(str(frame.filename).replace('\\', '/').endswith(suffix) for frame in inspect.stack())
    except Exception:
        return False


def _called_from_pro_predictor() -> bool:
    return _called_from_page('pro_predictor.py')


def _called_from_simulation_lab() -> bool:
    return _called_from_page('simulation_lab.py')


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


def _label_key(label: Any) -> str:
    return ' '.join(str(label or '').lower().replace('%', '').replace('±', '').split())


def _slider_should_use_number_input(label: Any) -> bool:
    key = _label_key(label)
    return 'agent score' in key or 'puntaje agente' in key


def _pro_predictor_number_defaults(label: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Make Pro Predictor default to a controlled 500-event workflow.

    The page source still defines conservative caps. This wrapper lifts the input caps at
    runtime without changing model logic. Target scan: 5 sports × 100 events = ~500 events.
    """
    key = _label_key(label)
    out = dict(kwargs)
    if key in {'max sports', 'máximo de deportes', 'maximo de deportes'}:
        out['max_value'] = max(int(out.get('max_value', 120)), 250)
        out['value'] = min(max(int(out.get('value', 5)), 5), int(out['max_value']))
        out['step'] = 1
    elif key in {'max events per sport', 'máximo de eventos por deporte', 'maximo de eventos por deporte'}:
        out['max_value'] = max(int(out.get('max_value', 100)), 500)
        out['value'] = min(max(int(out.get('value', 100)), 100), int(out['max_value']))
        out['step'] = 25
    elif key in {'max high-confidence rows', 'máximo de filas de máxima confianza', 'maximo de filas de maxima confianza'}:
        out['max_value'] = max(int(out.get('max_value', 100)), 500)
        out['value'] = min(max(int(out.get('value', 500)), 500), int(out['max_value']))
        out['step'] = 25
    elif key in {'minimum books', 'mínimo de casas', 'minimo de casas'}:
        out['value'] = min(max(int(out.get('value', 1)), 1), int(out.get('max_value', 25)))
        out['step'] = 1
    elif key in {'minimum model probability', 'probabilidad mínima del modelo', 'probabilidad minima del modelo'}:
        out['value'] = min(max(float(out.get('value', 0.60)), 0.60), float(out.get('max_value', 0.99)))
        out['step'] = 0.01
    elif key in {'minimum edge', 'ventaja mínima', 'ventaja minima'}:
        out['value'] = max(float(out.get('min_value', -0.25)), min(float(out.get('value', -0.02)), float(out.get('max_value', 0.50))))
        out['step'] = 0.005
        out.setdefault('format', '%.3f')
    elif key in {'strong edge threshold', 'umbral de ventaja fuerte'}:
        out['value'] = max(float(out.get('min_value', 0.0)), min(float(out.get('value', 0.03)), float(out.get('max_value', 0.50))))
        out['step'] = 0.005
        out.setdefault('format', '%.3f')
    return out


def _simulation_number_defaults(label: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    key = _label_key(label)
    out = dict(kwargs)
    if key in {'iterations', 'iteraciones'}:
        out['value'] = min(float(out.get('value', 1000)), 1000)
        out['max_value'] = min(float(out.get('max_value', 5000)), 5000)
        out['step'] = 500
    elif 'max rows per strategy' in key or 'max filas por estrategia' in key or 'maximo filas por estrategia' in key or 'max filas' in key or 'máx filas' in key:
        out['value'] = min(int(out.get('value', 50)), 50)
        out['max_value'] = min(int(out.get('max_value', 250)), 250)
        out['step'] = 25
    elif 'minimum optimizer rows' in key or 'minimo de filas del optimizador' in key or 'mínimo de filas del optimizador' in key:
        out['value'] = min(int(out.get('value', 3)), 3)
        out['max_value'] = min(int(out.get('max_value', 50)), 50)
        out['step'] = 1
    return out


def _install_page_helpers() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_page_helpers_installed_v5', False):
        return
    st._aba_page_helpers_installed_v5 = True
    real_st_dataframe = st.dataframe
    real_dg_dataframe = DeltaGenerator.dataframe
    real_subheader = st.subheader
    real_st_slider = st.slider
    real_dg_slider = DeltaGenerator.slider
    real_st_number_input = st.number_input
    real_dg_number_input = DeltaGenerator.number_input
    real_st_download_button = st.download_button
    real_dg_download_button = getattr(DeltaGenerator, 'download_button', None)

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

    def pro_predictor_download_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
        out = dict(kwargs)
        if _called_from_pro_predictor():
            out.setdefault('on_click', 'ignore')
        return out

    def patched_st_dataframe(data: Any = None, *args: Any, **kwargs: Any) -> Any:
        captured = capture(data)
        if render_mobile_predictor_report is not None and should_render_mobile(captured):
            return render_mobile_predictor_report(captured, table_renderer=real_st_dataframe)
        return real_st_dataframe(data, *args, **kwargs)

    def patched_dg_dataframe(self: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        capture(data)
        return real_dg_dataframe(self, data, *args, **kwargs)

    def patched_st_download_button(label: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        kwargs = pro_predictor_download_kwargs(kwargs)
        try:
            return real_st_download_button(label, data, *args, **kwargs)
        except TypeError:
            if kwargs.get('on_click') == 'ignore':
                fallback = dict(kwargs)
                fallback.pop('on_click', None)
                return real_st_download_button(label, data, *args, **fallback)
            raise

    def patched_dg_download_button(self: Any, label: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        if real_dg_download_button is None:
            return patched_st_download_button(label, data, *args, **kwargs)
        kwargs = pro_predictor_download_kwargs(kwargs)
        try:
            return real_dg_download_button(self, label, data, *args, **kwargs)
        except TypeError:
            if kwargs.get('on_click') == 'ignore':
                fallback = dict(kwargs)
                fallback.pop('on_click', None)
                return real_dg_download_button(self, label, data, *args, **fallback)
            raise

    def patched_st_number_input(label: Any, *args: Any, **kwargs: Any) -> Any:
        if _called_from_pro_predictor():
            kwargs = _pro_predictor_number_defaults(label, kwargs)
        elif _called_from_simulation_lab():
            kwargs = _simulation_number_defaults(label, kwargs)
        return real_st_number_input(label, *args, **kwargs)

    def patched_dg_number_input(self: Any, label: Any, *args: Any, **kwargs: Any) -> Any:
        if _called_from_pro_predictor():
            kwargs = _pro_predictor_number_defaults(label, kwargs)
        elif _called_from_simulation_lab():
            kwargs = _simulation_number_defaults(label, kwargs)
        return real_dg_number_input(self, label, *args, **kwargs)

    def patched_st_slider(label: Any, *args: Any, **kwargs: Any) -> Any:
        if _called_from_pro_predictor() and _slider_should_use_number_input(label):
            kwargs = _pro_predictor_number_defaults(label, kwargs)
            return real_st_number_input(label, *args, **kwargs)
        return real_st_slider(label, *args, **kwargs)

    def patched_dg_slider(self: Any, label: Any, *args: Any, **kwargs: Any) -> Any:
        if _called_from_pro_predictor() and _slider_should_use_number_input(label):
            kwargs = _pro_predictor_number_defaults(label, kwargs)
            return real_dg_number_input(self, label, *args, **kwargs)
        return real_dg_slider(self, label, *args, **kwargs)

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
    st.download_button = patched_st_download_button
    if real_dg_download_button is not None:
        DeltaGenerator.download_button = patched_dg_download_button
    st.number_input = patched_st_number_input
    DeltaGenerator.number_input = patched_dg_number_input
    st.slider = patched_st_slider
    DeltaGenerator.slider = patched_dg_slider
    st.subheader = patched_subheader


_install_page_helpers()

"""Autonomous Betting Agent.

A standalone, research-only sports analytics agent derived from the ARA/TGRM
architecture. It estimates probabilities, explains evidence, tracks uncertainty,
learns probability calibration from graded results, tracks edge/profit/CLV, and
supports backtesting.
"""

from __future__ import annotations

from typing import Any

from .learning import GradedPrediction, ProbabilityCalibrator, fit_probability_calibrator, parse_graded_csv
from .models import EventResearchInput, PredictionResult, TeamSnapshot
from .researcher import AutonomousBettingAgent
from .tgrm import TGRMLoop
from .tracking import PredictionLedgerRow, SelectionDecision, SelectionPolicy, TrackingReport, choose_decision, summarize_tracking

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
PREDICTOR_TOOL_NAME = 'Pro Predictor'


def _install_streamlit_helpers() -> None:
    """Install global Spanish/English navigation, explainers, CSV downloads, and light table translation."""
    try:
        import inspect
        import io
        import pandas as pd
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    if getattr(st, '_aba_streamlit_helpers_v13_installed', False):
        return
    st._aba_streamlit_helpers_v13_installed = True

    page_language_keys = [
        'global_language', 'app_language', 'language_settings_language', 'start_here_language',
        'tool_command_center_language', 'command_center_language', 'game_intelligence_language',
        'deployment_health_language', 'scanner_pro_language', 'pro_predictor_language',
        'ultra80_profit_mode_language', 'simulation_lab_language', 'threshold_optimizer_language',
        'what_are_the_odds_language', 'what_are_the_odds_pro_language', 'odds_lock_pro_language',
        'public_proof_dashboard_language', 'auto_result_grading_language', 'daily_workflow_language',
        'learning_memory_language', 'learn_memory_language', 'monthly_license_readiness_language',
        'buyer_demo_mode_language', 'daily_operator_checklist_language', 'private_beta_sales_dashboard_language',
        'reset_data_language', 'reset_lock_file_language',
    ]

    tools: tuple[tuple[str, str, str], ...] = (
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
    notes_en = (
        'Commercial workflow: Scanner Pro → Pro Predictor → Ultra 70 Profit Mode → Odds Lock Pro → Public Proof Dashboard → Threshold Optimizer → Learning Memory.',
        'Use Scanner Pro for live market discovery.',
        'Use Pro Predictor for final all-sports prediction scoring.',
        'Use Ultra 70 Profit Mode to send 70%+ lockable rows to Odds Lock Pro while keeping strict 80 proof separate.',
        'Use Simulation Lab to stress-test ROI, hit rate, drawdown, and overconfidence risk before locking.',
        'Use Odds Lock Pro to create timestamped proof rows before results are known.',
        'Use Public Proof Dashboard for client-safe metrics, result uploads, persistent ledger storage, and report cards.',
        'Use Reset Lock File to clear one test-window proof ledger without touching other test windows.',
        'Use Threshold Optimizer after results finish to learn the best cutoffs and false-positive patterns.',
        'Use Learning Memory for durable training and saved model memory.',
    )
    notes_es = (
        'Flujo comercial: Scanner Pro → Pro Predictor → Ultra 70 Profit Mode → Bloqueo de Cuotas Pro → Dashboard Público de Prueba → Optimizador de Umbrales → Memoria de Aprendizaje.',
        'Usa Scanner Pro para descubrir mercados en vivo.',
        'Usa Pro Predictor para la calificación final de predicciones en todos los deportes.',
        'Usa Ultra 70 Profit Mode para enviar filas bloqueables 70%+ a Odds Lock Pro y mantener la prueba estricta 80 separada.',
        'Usa Laboratorio de Simulación para probar ROI, acierto, drawdown y riesgo de sobreconfianza antes de bloquear.',
        'Usa Bloqueo de Cuotas Pro para crear filas de prueba con timestamp antes de conocer resultados.',
        'Usa Dashboard Público de Prueba para métricas seguras para clientes, resultados, ledger persistente y tarjetas de reporte.',
        'Usa Reiniciar Archivo de Bloqueo para borrar el ledger de una ventana de prueba sin tocar las demás.',
        'Usa Optimizador de Umbrales después de los resultados para aprender mejores cortes y falsos positivos.',
        'Usa Memoria de Aprendizaje para entrenamiento duradero y memoria guardada del modelo.',
    )

    es_columns = {
        'stage': 'etapa', 'session_key': 'clave_sesion', 'rows': 'filas', 'event': 'evento', 'sport': 'deporte',
        'market_type': 'tipo_mercado', 'prediction': 'pronostico', 'model_probability': 'probabilidad_modelo',
        'decimal_price': 'cuota_decimal', 'best_available_price': 'mejor_cuota_disponible',
        'best_available_book': 'mejor_casa', 'edge_percent': 'ventaja_pct', 'expected_value_percent': 'ev_pct',
        'robust_expected_value_percent': 'ev_robusto_pct', 'result_status': 'estado_resultado', 'winner': 'ganador',
        'final_score': 'marcador_final', 'proof_id': 'id_prueba', 'locked_at_utc': 'hora_bloqueo_utc',
        'closing_decimal_price': 'cuota_cierre_decimal', 'closing_value_percent': 'clv_pct',
        'beat_closing_price': 'supero_cierre', 'hit_rate': 'tasa_acierto', 'wins': 'victorias', 'losses': 'derrotas',
        'resolved': 'resueltos', 'pending': 'pendientes', 'profit_units': 'unidades_ganancia', 'stake_units': 'unidades_apostadas',
        'ultra80_candidate': 'candidato_ultra80', 'ultra80_profit_mode': 'modo_ultra80_rentable',
        'ultra80_profit_at_80_percent': 'ganancia_al_80_pct', 'ultra80_reasons': 'razones_ultra80',
        'volume_tier': 'nivel_volumen', 'min_probability': 'probabilidad_minima', 'min_edge': 'ventaja_minima',
        'min_ev': 'ev_minimo', 'min_books': 'casas_minimas', 'min_api_coverage': 'cobertura_api_minima',
        'min_agent_score': 'puntaje_agente_minimo', 'false_positive': 'falso_positivo',
        'mean_roi': 'roi_promedio', 'profit_probability': 'probabilidad_ganancia', 'prob_hit_80_plus': 'prob_acierto_80_mas',
    }
    es_values = {
        'win': 'victoria', 'loss': 'derrota', 'void': 'nulo', 'pending': 'pendiente', 'unknown': 'pendiente',
        'True': 'Verdadero', 'False': 'Falso', 'true': 'verdadero', 'false': 'falso',
        'play_strong': 'jugar_fuerte', 'play_small': 'jugar_pequeño', 'watch_only': 'solo_observar',
        'no_action': 'sin_accion', 'review_needed': 'requiere_revision', 'lock_candidate': 'candidato_bloqueo',
        'shortlist_review': 'revisar_lista_corta', 'needs_more_info': 'falta_mas_info', 'rescan_prices': 'reescanear_cuotas',
        'skip': 'omitir', 'rough_learning_memory': 'memoria_inicial', 'usable_learning_memory': 'memoria_utilizable',
        'strong_learning_memory': 'memoria_fuerte', 'not_ready': 'no_lista', 'PASS': 'APROBADO', 'FAIL': 'RECHAZADO',
        'B_ultra70_lockable': 'B_ultra70_bloqueable', 'A_strict_80_proof': 'A_prueba_80_estricta',
    }

    def normalize_language(value: object) -> str:
        text = str(value or '').strip().lower()
        if text.startswith('es') or 'español' in text or 'espanol' in text:
            return 'Español'
        if text.startswith('en') or 'english' in text:
            return 'English'
        return ''

    def query_language() -> str:
        try:
            value = st.query_params.get('lang', '')
            if isinstance(value, list):
                value = value[0] if value else ''
            return normalize_language(value)
        except Exception:
            return ''

    def safe_set_state(key: str, value: str) -> None:
        try:
            st.session_state[key] = value
        except Exception:
            pass

    def save_language(value: object) -> str:
        selected = normalize_language(value) or 'Español'
        for key in page_language_keys:
            safe_set_state(key, selected)
        try:
            st.query_params['lang'] = 'es' if selected == 'Español' else 'en'
        except Exception:
            pass
        return selected

    def language_value() -> str:
        values = [normalize_language(st.session_state.get(key)) for key in page_language_keys if normalize_language(st.session_state.get(key))]
        if 'Español' in values:
            return save_language('Español')
        if 'English' in values:
            return save_language('English')
        query = query_language()
        if query == 'Español':
            return save_language('Español')
        try:
            default = normalize_language(st.secrets.get('DEFAULT_LANGUAGE', ''))
        except Exception:
            default = ''
        return save_language(default or 'Español')

    def translate_value(value: Any) -> Any:
        if language_value() != 'Español' or value is None:
            return value
        return es_values.get(str(value), str(value))

    def translate_frame(data: Any) -> Any:
        if language_value() != 'Español' or not isinstance(data, pd.DataFrame):
            return data
        frame = data.copy()
        for col in frame.columns:
            if frame[col].dtype == object:
                frame[col] = frame[col].map(translate_value)
        return frame.rename(columns={str(col): es_columns.get(str(col), str(col)) for col in frame.columns})

    def translate_csv_text(data: Any) -> Any:
        if language_value() != 'Español':
            return data
        try:
            if isinstance(data, bytes):
                text = data.decode('utf-8')
                was_bytes = True
            elif isinstance(data, str):
                text = data
                was_bytes = False
            else:
                return data
            translated = translate_frame(pd.read_csv(io.StringIO(text))).to_csv(index=False)
            return translated.encode('utf-8') if was_bytes else translated
        except Exception:
            return data

    def called_from_page(page_name: str) -> bool:
        try:
            return any(str(frame.filename).replace('\\', '/').endswith(f'pages/{page_name}') for frame in inspect.stack())
        except Exception:
            return False

    def called_from_pro_predictor() -> bool:
        return called_from_page('pro_predictor.py')

    def label_key(label: Any) -> str:
        return ' '.join(str(label or '').lower().replace('-', ' ').replace('_', ' ').replace('%', '').replace('±', '').split())

    def looks_like_predictor_table(data: Any) -> bool:
        if not isinstance(data, pd.DataFrame) or data.empty:
            return False
        keys = {str(col).strip().lower().replace(' ', '_') for col in data.columns}
        return 'event' in keys and 'prediction' in keys and bool({'model_probability_clean', 'model_probability', 'market_probability'} & keys)

    def simple_signature(data: pd.DataFrame) -> str:
        columns = ','.join(str(col) for col in data.columns[:18])
        raw = f'{len(data)}:{columns}'
        return str(sum(ord(char) for char in raw) % 1000000)

    def render_pro_predictor_download(data: Any) -> None:
        if not called_from_pro_predictor() or not looks_like_predictor_table(data):
            return
        signature = simple_signature(data)
        rendered = st.session_state.setdefault('_aba_pro_predictor_visible_csv_buttons', set())
        if signature in rendered:
            return
        rendered.add(signature)
        label = 'Download this Pro Predictor CSV' if language_value() == 'English' else 'Descargar este CSV de Pro Predictor'
        filename = f'pro_predictor_export_{len(data)}_rows.csv'
        st.download_button(label, data.to_csv(index=False), file_name=filename, mime='text/csv', key=f'pro_predictor_visible_csv_{signature}')

    def slider_should_use_number_input(label: Any) -> bool:
        key = label_key(label)
        return 'agent score' in key or 'puntaje agente' in key

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
            st.markdown('---')
            st.markdown('### Flujo' if lang == 'Español' else '### Workflow')
            for note in (notes_es if lang == 'Español' else notes_en):
                st.caption(note)

    real_set_page_config = st.set_page_config
    real_st_selectbox = st.selectbox
    real_dg_selectbox = DeltaGenerator.selectbox
    real_st_number_input = st.number_input
    real_dg_number_input = DeltaGenerator.number_input
    real_st_slider = st.slider
    real_dg_slider = DeltaGenerator.slider
    real_st_dataframe = st.dataframe
    real_dg_dataframe = DeltaGenerator.dataframe
    real_st_table = st.table
    real_dg_table = DeltaGenerator.table
    real_st_download_button = st.download_button
    real_dg_download_button = DeltaGenerator.download_button

    def patched_set_page_config(*args: Any, **kwargs: Any) -> Any:
        if not args:
            kwargs.setdefault('page_title', APP_NAME)
            kwargs.setdefault('initial_sidebar_state', 'expanded')
        return real_set_page_config(*args, **kwargs)

    def language_selectbox(label: Any, options: Any, args: tuple[Any, ...], kwargs: dict[str, Any], original: Any, target: Any = None) -> Any:
        label_text = str(label or '').lower()
        opts = list(options)
        is_language = ('language' in label_text or 'idioma' in label_text or 'translate page' in label_text) and 'English' in opts and 'Español' in opts
        if not is_language:
            if target is None:
                return original(label, options, *args, **kwargs)
            return original(target, label, options, *args, **kwargs)
        kwargs = dict(kwargs)
        widget_key = kwargs.get('key') or 'global_language'
        kwargs['key'] = widget_key
        current = normalize_language(st.session_state.get(widget_key)) or language_value()
        kwargs['index'] = opts.index(current) if current in opts else opts.index('Español')
        selector_label = 'Idioma' if current == 'Español' else 'Language'
        if target is None:
            value = original(selector_label, opts, *args, **kwargs)
        else:
            value = original(target, selector_label, opts, *args, **kwargs)
        selected = save_language(value)
        render_nav(selected)
        return selected

    def number_input_with_pro_caps(label: Any, args: tuple[Any, ...], kwargs: dict[str, Any], original: Any, target: Any = None) -> Any:
        if called_from_pro_predictor() and label_key(label) in {'max sports', 'max events per sport', 'max high confidence rows', 'máximo de filas de máxima confianza'}:
            kwargs = dict(kwargs)
            kwargs['max_value'] = 500
            if kwargs.get('value', 0) and kwargs['value'] > 500:
                kwargs['value'] = 500
        if target is None:
            return original(label, *args, **kwargs)
        return original(target, label, *args, **kwargs)

    def slider_with_agent_score_number(label: Any, args: tuple[Any, ...], kwargs: dict[str, Any], original_slider: Any, original_number: Any, target: Any = None) -> Any:
        if called_from_pro_predictor() and slider_should_use_number_input(label):
            if target is None:
                return original_number(label, *args, **kwargs)
            return original_number(target, label, *args, **kwargs)
        if target is None:
            return original_slider(label, *args, **kwargs)
        return original_slider(target, label, *args, **kwargs)

    def patched_st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return language_selectbox(label, options, args, kwargs, real_st_selectbox)

    def patched_dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return language_selectbox(label, options, args, kwargs, real_dg_selectbox, target=self)

    def patched_st_number_input(label: Any, *args: Any, **kwargs: Any) -> Any:
        return number_input_with_pro_caps(label, args, kwargs, real_st_number_input)

    def patched_dg_number_input(self: Any, label: Any, *args: Any, **kwargs: Any) -> Any:
        return number_input_with_pro_caps(label, args, kwargs, real_dg_number_input, target=self)

    def patched_st_slider(label: Any, *args: Any, **kwargs: Any) -> Any:
        return slider_with_agent_score_number(label, args, kwargs, real_st_slider, real_st_number_input)

    def patched_dg_slider(self: Any, label: Any, *args: Any, **kwargs: Any) -> Any:
        return slider_with_agent_score_number(label, args, kwargs, real_dg_slider, real_dg_number_input, target=self)

    def patched_st_dataframe(data: Any = None, *args: Any, **kwargs: Any) -> Any:
        render_pro_predictor_download(data)
        return real_st_dataframe(translate_frame(data), *args, **kwargs)

    def patched_dg_dataframe(self: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        render_pro_predictor_download(data)
        return real_dg_dataframe(self, translate_frame(data), *args, **kwargs)

    def patched_st_table(data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_st_table(translate_frame(data), *args, **kwargs)

    def patched_dg_table(self: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_dg_table(self, translate_frame(data), *args, **kwargs)

    def patched_st_download_button(label: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_st_download_button(label, translate_csv_text(data), *args, **kwargs)

    def patched_dg_download_button(self: Any, label: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_dg_download_button(self, label, translate_csv_text(data), *args, **kwargs)

    st.set_page_config = patched_set_page_config
    st.selectbox = patched_st_selectbox
    DeltaGenerator.selectbox = patched_dg_selectbox
    st.number_input = patched_st_number_input
    DeltaGenerator.number_input = patched_dg_number_input
    st.slider = patched_st_slider
    DeltaGenerator.slider = patched_dg_slider
    st.dataframe = patched_st_dataframe
    DeltaGenerator.dataframe = patched_dg_dataframe
    st.table = patched_st_table
    DeltaGenerator.table = patched_dg_table
    st.download_button = patched_st_download_button
    DeltaGenerator.download_button = patched_dg_download_button


_install_streamlit_helpers()

__all__ = [
    'AutonomousBettingAgent', 'EventResearchInput', 'GradedPrediction', 'PredictionLedgerRow',
    'PredictionResult', 'ProbabilityCalibrator', 'SelectionDecision', 'SelectionPolicy',
    'TeamSnapshot', 'TGRMLoop', 'TrackingReport', 'choose_decision', 'fit_probability_calibrator',
    'parse_graded_csv', 'summarize_tracking',
]

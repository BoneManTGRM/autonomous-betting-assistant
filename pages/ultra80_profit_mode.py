from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import build_agent_decisions, ultra80_candidates
from autonomous_betting_agent.four_tool_orchestrator import page_health, page_health_frame

st.set_page_config(page_title='Ultra 80 Profit Mode', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='ultra80_profit_mode_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Ultra 80 Profit Mode',
        'caption': 'Strict shortlist mode built for two goals: 80%+ consistency target and positive expected profit. This mode intentionally kills volume.',
        'source': 'Prediction source', 'session': 'Use latest Pro Predictor session', 'upload': 'Upload Pro Predictor CSV', 'upload_label': 'Upload CSV',
        'run': 'Build Ultra 80 shortlist', 'no_rows': 'No rows available. Run Pro Predictor first or upload a CSV.', 'no_pass': 'No rows passed Ultra 80 Profit Mode. That is normal when the filters are strict.',
        'all_rows': 'All reviewed rows', 'ultra_rows': 'Ultra 80 passed rows', 'download': 'Download Ultra 80 CSV', 'download_all': 'Download reviewed CSV',
        'rows': 'Rows reviewed', 'passed': 'Passed Ultra 80', 'avg_prob': 'Avg model probability', 'avg_ev': 'Avg EV/unit', 'avg_profit80': 'Avg profit at 80%', 'next': 'Next action',
        'rules': 'Rules enforced', 'rule_text': 'Requires 80%+ model probability, profitable odds at 80%, positive EV, strong edge, 6+ books, enough API coverage, no draw picks, no bad timing, no negative line movement, and no negative memory pattern.',
        'saved': 'Ultra 80 rows saved as the active handoff list for Odds Lock Pro.', 'proof': 'Lock these before start time. Do not count picks that were not timestamped before the event.',
    },
    'es': {
        'title': 'Modo Ultra 80 Rentable',
        'caption': 'Lista corta estricta para dos metas: objetivo de 80%+ constante y ganancia esperada positiva. Este modo reduce mucho el volumen.',
        'source': 'Fuente de predicciones', 'session': 'Usar última sesión de Predictor Pro', 'upload': 'Subir CSV de Predictor Pro', 'upload_label': 'Subir CSV',
        'run': 'Crear lista Ultra 80', 'no_rows': 'No hay filas disponibles. Ejecuta Predictor Pro primero o sube un CSV.', 'no_pass': 'Ninguna fila pasó el Modo Ultra 80 Rentable. Eso es normal con filtros estrictos.',
        'all_rows': 'Todas las filas revisadas', 'ultra_rows': 'Filas aprobadas Ultra 80', 'download': 'Descargar CSV Ultra 80', 'download_all': 'Descargar CSV revisado',
        'rows': 'Filas revisadas', 'passed': 'Aprobadas Ultra 80', 'avg_prob': 'Probabilidad promedio', 'avg_ev': 'EV promedio/unidad', 'avg_profit80': 'Ganancia promedio al 80%', 'next': 'Siguiente acción',
        'rules': 'Reglas aplicadas', 'rule_text': 'Requiere 80%+ probabilidad del modelo, cuotas rentables al 80%, EV positivo, ventaja fuerte, 6+ casas, suficiente cobertura API, sin empates, buen timing, sin movimiento de línea negativo y sin patrón de memoria negativo.',
        'saved': 'Filas Ultra 80 guardadas como lista activa para Odds Lock Pro.', 'proof': 'Bloquéalas antes del inicio. No cuentes picks sin timestamp antes del evento.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: Any) -> str:
    number = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(number):
        return 'N/A'
    return f'{float(number) * 100:.1f}%'


def load_session_frame() -> pd.DataFrame:
    for key in ('pro_predictor_all_rows', 'pro_predictor_high_confidence_rows', 'pro_predictor_latest_rows', 'ara_latest_predictions'):
        rows = st.session_state.get(key)
        if isinstance(rows, list) and rows:
            return pd.DataFrame(rows)
    return pd.DataFrame()


def clean_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors='coerce')
    if 'prob' in column.lower() or column in {'ultra80_profit_at_80_percent', 'profit_at_80_percent', 'expected_value_per_unit'}:
        values = values.where(values <= 1.0, values / 100.0)
    return values


def source_frame() -> tuple[pd.DataFrame, str]:
    choice = st.radio(t('source'), [t('session'), t('upload')], horizontal=True)
    if choice == t('upload'):
        upload = st.file_uploader(t('upload_label'), type=['csv'], key='ultra80_upload_csv')
        if upload is None:
            return pd.DataFrame(), 'upload'
        try:
            return pd.read_csv(upload), getattr(upload, 'name', 'uploaded_csv')
        except Exception as exc:
            st.error(str(exc))
            return pd.DataFrame(), 'upload_error'
    return load_session_frame(), 'session'


st.title(t('title'))
st.caption(t('caption'))
with st.expander(t('rules'), expanded=True):
    st.write(t('rule_text'))
    st.warning(t('proof'))

frame, source = source_frame()
if st.button(t('run'), type='primary', use_container_width=True):
    if frame.empty:
        st.info(t('no_rows'))
        st.stop()
    reviewed = build_agent_decisions(frame)
    ultra = reviewed[reviewed.get('ultra80_candidate', pd.Series(index=reviewed.index, dtype=bool)).fillna(False).astype(bool)].copy()
    if not ultra.empty:
        sort_cols = [col for col in ['agent_score', 'model_probability_clean', 'expected_value_per_unit', 'ultra80_profit_at_80_percent', 'model_market_edge'] if col in ultra.columns]
        ultra = ultra.sort_values(sort_cols, ascending=False, na_position='last') if sort_cols else ultra
        st.session_state['ultra80_profit_mode_rows'] = ultra.to_dict('records')
        st.session_state['pro_predictor_latest_rows'] = ultra.to_dict('records')
        st.session_state['ara_latest_predictions'] = ultra.to_dict('records')
        st.session_state['ara_latest_predictions_source'] = 'Ultra 80 Profit Mode'
        st.success(t('saved'))
    else:
        st.warning(t('no_pass'))
    metrics = st.columns(6)
    metrics[0].metric(t('rows'), len(reviewed))
    metrics[1].metric(t('passed'), len(ultra))
    metrics[2].metric(t('avg_prob'), pct(clean_numeric(ultra, 'model_probability_clean').mean()) if not ultra.empty else 'N/A')
    metrics[3].metric(t('avg_ev'), pct(clean_numeric(ultra, 'expected_value_per_unit').mean()) if not ultra.empty else 'N/A')
    metrics[4].metric(t('avg_profit80'), pct(clean_numeric(ultra, 'ultra80_profit_at_80_percent').mean()) if not ultra.empty else 'N/A')
    health = page_health(ultra if not ultra.empty else reviewed, page='ultra80_profit_mode')
    metrics[5].metric(t('next'), health.get('next_action', 'review'))
    display_cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'model_probability_clean', 'decimal_price', 'market_implied_probability', 'model_market_edge', 'expected_value_per_unit', 'ultra80_profit_at_80_percent', 'bookmaker_count', 'api_coverage_score', 'pattern_ara_memory_signal', 'line_value_signal', 'agent_score', 'recommended_stake_units', 'ultra80_signals', 'ultra80_reasons'] if col in reviewed.columns]
    tabs = st.tabs([t('ultra_rows'), t('all_rows')])
    with tabs[0]:
        if ultra.empty:
            st.info(t('no_pass'))
        else:
            st.dataframe(ultra[display_cols] if display_cols else ultra, use_container_width=True, hide_index=True)
            st.download_button(t('download'), ultra.to_csv(index=False), file_name='ultra80_profit_mode.csv', mime='text/csv')
            st.subheader('Handoff health')
            st.dataframe(page_health_frame(ultra, page='ultra80_profit_mode'), use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(reviewed[display_cols] if display_cols else reviewed, use_container_width=True, hide_index=True)
        st.download_button(t('download_all'), reviewed.to_csv(index=False), file_name='ultra80_reviewed_all_rows.csv', mime='text/csv')

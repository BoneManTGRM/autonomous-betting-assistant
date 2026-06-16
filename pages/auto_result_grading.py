from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from autonomous_betting_agent.auto_result_grading_tools import (
    grade_persistent_ledger_with_results,
    grading_summary,
    normalize_result_feed,
    odds_scores_to_result_frame,
    result_upload_template,
)
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, save_persistent_ledger
from autonomous_betting_agent.live_odds import _get_json, validate_api_key
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar

st.set_page_config(page_title='Auto Result Grading', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='auto_result_grading_language') == 'Español' else 'en'
render_tool_sidebar('auto_result_grading', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Auto Result Grading',
        'caption': 'Grade the persistent proof ledger from finished-result uploads or an explicit one-click score fetch.',
        'warning': 'No background calls run here. API score fetches happen only after pressing the fetch button.',
        'upload': 'Upload finished results CSV',
        'template': 'Download result upload template',
        'apply': 'Apply uploaded results to persistent ledger',
        'fetch': 'Fetch completed scores for one sport key',
        'sport_key': 'Sport key',
        'days_from': 'Days back',
        'api_key': 'Optional odds-data key override',
        'ledger': 'Current persistent ledger',
        'results': 'Normalized results preview',
        'summary': 'Grading summary',
        'saved': 'Saved updated persistent ledger',
    },
    'es': {
        'title': 'Autocalificación de Resultados',
        'caption': 'Califica el ledger persistente usando cargas de resultados finalizados o una búsqueda explícita de marcadores.',
        'warning': 'Aquí no corren llamadas en segundo plano. La búsqueda API solo corre al presionar el botón.',
        'upload': 'Subir CSV de resultados finalizados',
        'template': 'Descargar plantilla de resultados',
        'apply': 'Aplicar resultados subidos al ledger persistente',
        'fetch': 'Buscar marcadores finalizados para una sport key',
        'sport_key': 'Sport key',
        'days_from': 'Días atrás',
        'api_key': 'Llave opcional de datos de cuotas',
        'ledger': 'Ledger persistente actual',
        'results': 'Vista previa de resultados normalizados',
        'summary': 'Resumen de calificación',
        'saved': 'Ledger persistente actualizado guardado',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def get_key(override: str = '') -> str:
    key = override.strip()
    if key:
        return validate_api_key(key)
    try:
        key = str(st.secrets.get('THE_ODDS_API_KEY', '') or st.secrets.get('ODDS_API_KEY', '')).strip()
    except Exception:
        key = ''
    if not key:
        key = os.getenv('THE_ODDS_API_KEY', '') or os.getenv('ODDS_API_KEY', '')
    return validate_api_key(key)


st.title(t('title'))
st.caption(t('caption'))
st.warning(t('warning'))
ledger = load_persistent_ledger()
st.subheader(t('summary'))
st.json(grading_summary(ledger))

st.download_button(t('template'), result_upload_template().to_csv(index=False), file_name='result_upload_template.csv', mime='text/csv')
upload = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=False)
if upload is not None:
    result_frame = normalize_result_feed(pd.read_csv(upload))
    st.subheader(t('results'))
    st.dataframe(result_frame, use_container_width=True, hide_index=True)
    if st.button(t('apply'), type='primary', use_container_width=True):
        updated, stats = grade_persistent_ledger_with_results(result_frame)
        st.json(stats)
        if not updated.empty:
            st.success(t('saved'))

with st.expander(t('fetch'), expanded=False):
    sport_key = st.text_input(t('sport_key'), value='')
    days_from = st.number_input(t('days_from'), min_value=1, max_value=7, value=3, step=1)
    override = st.text_input(t('api_key'), value='', type='password')
    if st.button(t('fetch'), use_container_width=True) and sport_key.strip():
        try:
            payload = _get_json(f'/v4/sports/{sport_key.strip()}/scores/', {'apiKey': get_key(override), 'daysFrom': int(days_from), 'dateFormat': 'iso'})
            result_frame = odds_scores_to_result_frame(payload)
            st.dataframe(result_frame, use_container_width=True, hide_index=True)
            updated, stats = grade_persistent_ledger_with_results(result_frame)
            st.json(stats)
            if not updated.empty:
                save_persistent_ledger(updated)
                st.success(t('saved'))
        except Exception as exc:
            st.error(str(exc))

st.subheader(t('ledger'))
st.dataframe(ledger, use_container_width=True, hide_index=True)

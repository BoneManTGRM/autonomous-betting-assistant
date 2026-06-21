from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from autonomous_betting_agent.auto_result_grading_tools import grading_summary, result_upload_template
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger
from autonomous_betting_agent.live_odds import _get_json, validate_api_key
from autonomous_betting_agent.result_grading_v2 import grade_persistent_with_fuzzy, normalize_results, odds_scores_to_result_frame_v2
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar

st.set_page_config(page_title='Auto Result Grading V2', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='auto_result_grading_v2_language') == 'Español' else 'en'
render_tool_sidebar('auto_result_grading_v2', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Auto Result Grading V2',
        'caption': 'Improved grading: re-checks unresolved rows, checks all sport keys, fuzzy-matches events, and grades h2h/spreads/totals.',
        'summary': 'Grading summary',
        'template': 'Download result upload template',
        'upload': 'Upload finished results CSV',
        'results': 'Normalized results preview',
        'apply': 'Apply uploaded results with V2 fuzzy grader',
        'fetch': 'Fetch completed scores from API and grade',
        'all_sports': 'Fetch all sport keys found in ledger',
        'sport_key': 'Sport key',
        'days_from': 'Days back',
        'api_key': 'Optional odds-data key override',
        'saved': 'Saved updated persistent ledger',
        'ledger': 'Current persistent ledger',
    },
    'es': {
        'title': 'Autocalificación de Resultados V2',
        'caption': 'Calificación mejorada: revisa filas pendientes, todas las sport keys, empareja eventos y califica h2h/spreads/totals.',
        'summary': 'Resumen de calificación',
        'template': 'Descargar plantilla de resultados',
        'upload': 'Subir CSV de resultados finalizados',
        'results': 'Vista previa de resultados normalizados',
        'apply': 'Aplicar resultados con V2 fuzzy grader',
        'fetch': 'Buscar marcadores API y calificar',
        'all_sports': 'Buscar todas las sport keys del ledger',
        'sport_key': 'Sport key',
        'days_from': 'Días atrás',
        'api_key': 'Llave opcional de datos de cuotas',
        'saved': 'Ledger persistente actualizado guardado',
        'ledger': 'Ledger persistente actual',
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


def sport_keys_from_ledger(frame: pd.DataFrame) -> list[str]:
    keys: set[str] = set()
    for col in ('sport_key', 'sport'):
        if col in frame.columns:
            for value in frame[col].dropna().astype(str):
                text = value.strip()
                if text and '_' in text:
                    keys.add(text)
    return sorted(keys)


st.title(t('title'))
st.caption(t('caption'))
ledger = load_persistent_ledger()
st.subheader(t('summary'))
st.json(grading_summary(ledger))

st.download_button(t('template'), result_upload_template().to_csv(index=False), file_name='result_upload_template.csv', mime='text/csv')

upload = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=False)
if upload is not None:
    result_frame = normalize_results(pd.read_csv(upload))
    st.subheader(t('results'))
    st.dataframe(result_frame, use_container_width=True, hide_index=True)
    if st.button(t('apply'), type='primary', use_container_width=True):
        updated, stats = grade_persistent_with_fuzzy(result_frame)
        st.json(stats)
        if not updated.empty:
            ledger = load_persistent_ledger()
            st.success(t('saved'))

with st.expander(t('fetch'), expanded=True):
    fetch_all = st.checkbox(t('all_sports'), value=True)
    sport_key = st.text_input(t('sport_key'), value='', disabled=fetch_all)
    days_from = st.number_input(t('days_from'), min_value=1, max_value=7, value=3, step=1)
    override = st.text_input(t('api_key'), value='', type='password')
    if st.button(t('fetch'), use_container_width=True):
        try:
            api_key = get_key(override)
            keys = sport_keys_from_ledger(ledger) if fetch_all else ([sport_key.strip()] if sport_key.strip() else [])
            frames = []
            sport_stats = []
            for skey in keys:
                payload = _get_json(f'/v4/sports/{skey}/scores/', {'apiKey': api_key, 'daysFrom': int(days_from), 'dateFormat': 'iso'})
                frame = odds_scores_to_result_frame_v2(payload)
                sport_stats.append({'sport_key': skey, 'result_rows': int(len(frame))})
                if not frame.empty:
                    frames.append(frame)
            result_frame = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
            st.json({'sports_checked': sport_stats, 'total_result_rows': int(len(result_frame))})
            if not result_frame.empty:
                st.dataframe(result_frame, use_container_width=True, hide_index=True)
            updated, stats = grade_persistent_with_fuzzy(result_frame)
            st.json(stats)
            if not updated.empty:
                ledger = load_persistent_ledger()
                st.success(t('saved'))
        except Exception as exc:
            st.error(str(exc))

st.subheader(t('ledger'))
st.dataframe(ledger, use_container_width=True, hide_index=True)

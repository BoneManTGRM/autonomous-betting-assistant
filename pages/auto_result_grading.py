from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from autonomous_betting_agent.auto_result_grading_tools import grading_summary, result_upload_template
from autonomous_betting_agent.closing_line_tools import collect_closing_lines, collect_closing_lines_for_all_sports
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, save_persistent_ledger
from autonomous_betting_agent.dashboard_sync import sync_dashboard_state
from autonomous_betting_agent.live_odds import _get_json, validate_api_key
from autonomous_betting_agent.result_grading_v2 import grade_persistent_with_fuzzy, normalize_results, odds_scores_to_result_frame_v2
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar

st.set_page_config(page_title='Auto Result Grading', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='auto_result_grading_language') == 'Español' else 'en'
render_tool_sidebar('auto_result_grading', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Auto Result Grading',
        'caption': 'V2 grading is built into this page: it re-checks pending rows, checks every sport key in the ledger, grades h2h/spread/total outcomes, saves the ledger, and syncs the dashboard.',
        'warning': 'No background calls run here. API score and closing-line fetches happen only after pressing a button.',
        'upload': 'Upload finished results CSV',
        'template': 'Download result upload template',
        'apply': 'Apply uploaded results with V2 fuzzy grader',
        'fetch': 'Fetch completed scores and grade',
        'fetch_all_sports': 'Fetch all sport keys found in ledger',
        'closing': 'Collect closing/current odds for CLV',
        'closing_help': 'Run this close to event start for pending locked picks. It saves the current market average as closing_decimal_price so the Public Proof Dashboard can calculate CLV.',
        'collect_closing': 'Collect closing odds for CLV',
        'all_sports': 'Auto-collect for all sport keys in ledger',
        'pending_only': 'Pending rows only',
        'sport_key': 'Sport key',
        'regions': 'Regions',
        'markets': 'Markets',
        'overwrite_closing': 'Overwrite existing closing prices',
        'days_from': 'Days back',
        'api_key': 'Optional odds-data key override',
        'ledger': 'Current persistent ledger',
        'results': 'Normalized results preview',
        'summary': 'Grading summary',
        'saved': 'Saved and synced dashboard ledger',
    },
    'es': {
        'title': 'Autocalificación de Resultados',
        'caption': 'V2 está integrado aquí: revisa pendientes, todas las sport keys, califica resultados, guarda el ledger y sincroniza el dashboard.',
        'warning': 'Aquí no corren llamadas en segundo plano. La búsqueda API solo corre al presionar un botón.',
        'upload': 'Subir CSV de resultados finalizados',
        'template': 'Descargar plantilla de resultados',
        'apply': 'Aplicar resultados con V2 fuzzy grader',
        'fetch': 'Buscar marcadores finalizados y calificar',
        'fetch_all_sports': 'Buscar todas las sport keys del ledger',
        'closing': 'Recolectar cuotas de cierre/actuales para CLV',
        'closing_help': 'Ejecuta esto cerca del inicio del evento para picks bloqueados pendientes. Guarda el promedio actual del mercado como closing_decimal_price para calcular CLV.',
        'collect_closing': 'Recolectar cuotas de cierre para CLV',
        'all_sports': 'Recolectar automáticamente para todas las sport keys del ledger',
        'pending_only': 'Solo filas pendientes',
        'sport_key': 'Sport key',
        'regions': 'Regiones',
        'markets': 'Mercados',
        'overwrite_closing': 'Sobrescribir cuotas de cierre existentes',
        'days_from': 'Días atrás',
        'api_key': 'Llave opcional de datos de cuotas',
        'ledger': 'Ledger persistente actual',
        'results': 'Vista previa de resultados normalizados',
        'summary': 'Resumen de calificación',
        'saved': 'Ledger guardado y dashboard sincronizado',
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
st.warning(t('warning'))
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
            ledger = sync_dashboard_state(updated)
            st.success(t('saved'))

with st.expander(t('fetch'), expanded=True):
    fetch_all = st.checkbox(t('fetch_all_sports'), value=True)
    sport_key = st.text_input(t('sport_key'), value='', key='score_sport_key', disabled=fetch_all)
    days_from = st.number_input(t('days_from'), min_value=1, max_value=7, value=7, step=1)
    override = st.text_input(t('api_key'), value='', type='password', key='score_api_key')
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
                ledger = sync_dashboard_state(updated)
                st.success(t('saved'))
        except Exception as exc:
            st.error(str(exc))

with st.expander(t('closing'), expanded=False):
    st.caption(t('closing_help'))
    all_sports = st.checkbox(t('all_sports'), value=True)
    closing_sport_key = st.text_input(t('sport_key'), value='', key='closing_sport_key', disabled=all_sports)
    regions = st.text_input(t('regions'), value='us,eu,uk', key='closing_regions')
    markets = st.text_input(t('markets'), value='h2h,spreads,totals', key='closing_markets')
    closing_override = st.text_input(t('api_key'), value='', type='password', key='closing_api_key')
    overwrite = st.checkbox(t('overwrite_closing'), value=False)
    pending_only = st.checkbox(t('pending_only'), value=True)
    if st.button(t('collect_closing'), type='primary', use_container_width=True):
        try:
            if all_sports:
                updated, stats = collect_closing_lines_for_all_sports(ledger, api_key=get_key(closing_override), regions=regions.strip() or 'us,eu,uk', markets=markets.strip() or 'h2h,spreads,totals', overwrite_existing=overwrite, pending_only=pending_only)
            elif closing_sport_key.strip():
                updated, stats = collect_closing_lines(ledger, api_key=get_key(closing_override), sport_key=closing_sport_key.strip(), regions=regions.strip() or 'us,eu,uk', markets=markets.strip() or 'h2h,spreads,totals', overwrite_existing=overwrite, pending_only=pending_only)
            else:
                updated, stats = pd.DataFrame(), {'updated_rows': 0, 'reason': 'missing_sport_key'}
            st.json(stats)
            if not updated.empty:
                save_persistent_ledger(updated)
                ledger = sync_dashboard_state(updated)
                status_cols = [col for col in ['event', 'prediction', 'result_status', 'closing_decimal_price', 'closing_collection_status', 'closing_match_confidence'] if col in ledger.columns]
                if status_cols:
                    st.dataframe(ledger[status_cols], use_container_width=True, hide_index=True)
                st.success(t('saved'))
        except Exception as exc:
            st.error(str(exc))

st.subheader(t('ledger'))
st.dataframe(ledger, use_container_width=True, hide_index=True)

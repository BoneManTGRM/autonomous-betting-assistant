from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.daily_workflow_tools import daily_workflow_preview, run_daily_workflow, workflow_stage_frame

st.set_page_config(page_title='One-Click Daily Workflow', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='daily_workflow_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'One-Click Daily Workflow',
        'caption': 'Take current prediction rows, lock qualified picks, optionally save them, and generate reports in one guided flow.',
        'use_session': 'Use latest session rows',
        'upload': 'Upload prediction CSV',
        'analyst': 'Analyst / brand',
        'max_units': 'Max units per pick',
        'include_watch': 'Include watch rows',
        'save': 'Save locked rows to persistent ledger',
        'language': 'Report language',
        'preview': 'Preview workflow readiness',
        'run': 'Run daily workflow',
        'stages': 'Workflow stages',
        'public': 'Public proof table',
        'report': 'Daily report',
        'card': 'Report card',
        'metrics': 'Metrics',
        'no_rows': 'No rows found. Use Scanner/Pro Predictor/What Are the Odds first, or upload a CSV.',
    },
    'es': {
        'title': 'Flujo Diario de Un Clic',
        'caption': 'Toma filas actuales, bloquea picks calificados, opcionalmente los guarda, y genera reportes en un flujo guiado.',
        'use_session': 'Usar últimas filas de sesión',
        'upload': 'Subir CSV de predicciones',
        'analyst': 'Analista / marca',
        'max_units': 'Máximo de unidades por pick',
        'include_watch': 'Incluir filas de vigilancia',
        'save': 'Guardar filas bloqueadas en ledger persistente',
        'language': 'Idioma del reporte',
        'preview': 'Vista previa de preparación',
        'run': 'Ejecutar flujo diario',
        'stages': 'Etapas del flujo',
        'public': 'Tabla pública de prueba',
        'report': 'Reporte diario',
        'card': 'Tarjeta de reporte',
        'metrics': 'Métricas',
        'no_rows': 'No hay filas. Usa Scanner/Pro Predictor/What Are the Odds primero, o sube un CSV.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def session_rows() -> list[dict]:
    for key in ['what_are_the_odds_latest_rows', 'pro_predictor_latest_rows', 'scanner_pro_latest_rows', 'ara_latest_predictions']:
        rows = st.session_state.get(key) or []
        if rows:
            return rows
    return []


st.title(t('title'))
st.caption(t('caption'))
frames = []
rows = session_rows()
if st.checkbox(t('use_session'), value=bool(rows)) and rows:
    frames.append(pd.DataFrame(rows))
uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
if uploads:
    for upload in uploads:
        frames.append(pd.read_csv(upload))
if not frames:
    st.warning(t('no_rows'))
    st.stop()

raw = pd.concat(frames, ignore_index=True, sort=False)
analyst = st.text_input(t('analyst'), value='Private Analytics')
max_units = st.number_input(t('max_units'), min_value=0.25, max_value=10.0, value=2.0, step=0.25)
include_watch = st.checkbox(t('include_watch'), value=False)
save = st.checkbox(t('save'), value=False)
report_language = st.radio(t('language'), ['English', 'Español'], horizontal=True, index=0 if LANG == 'en' else 1)

st.subheader(t('preview'))
st.json(daily_workflow_preview(raw, include_watch=include_watch))

if st.button(t('run'), type='primary', use_container_width=True):
    result = run_daily_workflow(raw, analyst=analyst, max_units=float(max_units), include_watch=include_watch, save_to_persistent=save, report_language=report_language)
    st.session_state['odds_lock_pro_locked_rows'] = result['locked_frame'].to_dict('records')
    st.subheader(t('stages'))
    st.dataframe(workflow_stage_frame(result), use_container_width=True, hide_index=True)
    st.subheader(t('metrics'))
    st.json(result['metrics'])
    st.subheader(t('public'))
    st.dataframe(result['public_frame'], use_container_width=True, hide_index=True)
    st.download_button('Download locked workflow CSV', result['locked_frame'].to_csv(index=False), file_name='daily_workflow_locked.csv', mime='text/csv')
    st.subheader(t('report'))
    st.text_area(t('report'), value=result['daily_report'], height=320)
    st.subheader(t('card'))
    st.text_area(t('card'), value=result['report_card'], height=240)

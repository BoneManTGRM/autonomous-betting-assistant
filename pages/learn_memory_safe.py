"""Learning evidence review. No fitting, replacement, publication or file writes."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from autonomous_betting_agent.learning_evidence_admission import load_evidence_json, review_learning_records
from autonomous_betting_agent.learning_memory_tools import read_compact_csv_bytes
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import render_upload_css

MEMORY_BANK_PATH = Path(__file__).resolve().parents[1] / 'data' / 'learning_memory_bank.json'
st.set_page_config(page_title='Learning Memory — Evidence Review', layout='wide')
LANG = render_app_sidebar('learning_memory', language_key='learning_memory_language', selector='radio')
render_upload_css(st, LANG)

TEXT = {
    'en': {
        'title': 'Learning Memory — Evidence Review',
        'mode': 'Observation only: this page does not train, replace memory, publish files, or change saved weights.',
        'trust': 'Supplied verification flags and source URLs are claims, not independently authenticated proof. Even complete claims cannot enable training or promotion.',
        'legacy': 'Existing learned weights remain in use unchanged. Their historical provenance is not certified by this review.',
        'upload': 'Upload original evidence CSV for review',
        'schema': 'Use the offline-learning-v1 evidence fields: original pre-event raw/baseline probabilities and model versions, event/market/selection IDs, prediction/result timestamps, source provenance, and an explicit final grade. Confidence labels and odds are not reconstructed predictions.',
        'include': 'Include existing memory records in the review (read only)',
        'run': 'Review learning readiness',
        'need': 'Upload an evidence CSV first.',
        'load_error': 'Existing memory could not be reviewed; no files were changed:',
        'parse_error': 'Upload could not be reviewed; original upload is unchanged:',
        'summary': 'Supplied rows / structurally admissible / rejected',
        'blocked': 'Evidence review blocked. No subset was trained and no artifacts were written.',
        'ready': 'Supplied claims meet structural readiness only. Independent verification and offline validation are still required. No training occurred.',
        'details': 'Every original record and indexed admission reason',
        'download': 'Download observation-only review JSON',
    },
    'es': {
        'title': 'Memoria de Aprendizaje — Revisión de evidencia',
        'mode': 'Solo observación: esta página no entrena, reemplaza memoria, publica archivos ni cambia pesos guardados.',
        'trust': 'Las marcas de verificación y URLs proporcionadas son afirmaciones, no pruebas autenticadas independientemente. Ni las afirmaciones completas permiten entrenar o promover modelos.',
        'legacy': 'Los pesos aprendidos existentes siguen aplicándose sin cambios. Esta revisión no certifica su procedencia histórica.',
        'upload': 'Subir CSV de evidencia original para revisión',
        'schema': 'Usa los campos de evidencia offline-learning-v1: probabilidades originales y base previas al evento, versiones de modelo, IDs de evento/mercado/selección, fechas de predicción/resultado, fuentes y resultado final explícito. Las etiquetas de confianza y cuotas no reconstruyen predicciones.',
        'include': 'Incluir registros de memoria existentes en la revisión (solo lectura)',
        'run': 'Revisar preparación del aprendizaje',
        'need': 'Primero sube un CSV de evidencia.',
        'load_error': 'No se pudo revisar la memoria existente; no se cambió ningún archivo:',
        'parse_error': 'No se pudo revisar la carga; el original permanece sin cambios:',
        'summary': 'Filas proporcionadas / estructuralmente admisibles / rechazadas',
        'blocked': 'Revisión de evidencia bloqueada. No se entrenó ningún subconjunto ni se escribió ningún archivo.',
        'ready': 'Las afirmaciones cumplen solo la preparación estructural. Aún requieren verificación independiente y validación offline. No hubo entrenamiento.',
        'details': 'Cada registro original y su motivo de admisión indexado',
        'download': 'Descargar JSON de revisión de solo observación',
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en'])[key]


st.title(t('title'))
st.info(t('mode'))
st.warning(t('trust'))
st.caption(t('legacy'))
st.caption(t('schema'))
uploaded = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=False, key='safe_learning_upload')
include_existing = st.checkbox(t('include'), value=True)

if st.button(t('run'), type='primary', use_container_width=True):
    if uploaded is None:
        st.warning(t('need'))
        st.stop()
    try:
        _preview, stats = read_compact_csv_bytes(uploaded.getvalue(), getattr(uploaded, 'name', 'uploaded.csv'))
        original_rows = [entry['record'] for entry in stats['admission_report']['records']]
    except (ValueError, TypeError) as exc:
        st.error(f"{t('parse_error')} {exc}")
        st.stop()
    existing_rows = []
    if include_existing and MEMORY_BANK_PATH.exists():
        try:
            bank = load_evidence_json(MEMORY_BANK_PATH.read_text(encoding='utf-8'))
            if not isinstance(bank, dict) or not isinstance(bank.get('compact_rows'), list):
                raise ValueError('compact_rows list required')
            existing_rows = bank['compact_rows']
        except (OSError, ValueError, TypeError) as exc:
            st.error(f"{t('load_error')} {exc}")
            st.stop()
    report = review_learning_records([*existing_rows, *original_rows])
    st.caption(t('summary'))
    cols = st.columns(3)
    for col, key in zip(cols, ('input_rows', 'admitted_rows', 'rejected_rows')):
        col.metric(key, report[key])
    if report['status'] == 'BLOCKED':
        st.warning(t('blocked'))
    else:
        st.info(t('ready'))
    st.write(report['reason'])
    st.dataframe(pd.DataFrame([{'row_index': entry['row_index'], 'admitted': entry['admitted'],
                               'reasons': '; '.join(entry['reasons'])} for entry in report['records']]),
                 use_container_width=True, hide_index=True)
    with st.expander(t('details')):
        st.json(report)
    st.download_button(t('download'), json.dumps(report, indent=2, ensure_ascii=False),
                       file_name='learning_evidence_review.json', mime='application/json')

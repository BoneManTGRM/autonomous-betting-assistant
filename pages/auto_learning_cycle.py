from __future__ import annotations

import json
import streamlit as st

from autonomous_betting_agent.auto_learning_cycle import run_auto_learning_cycle
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Learning Readiness Review', layout='wide')
LANG = render_app_sidebar('auto_learning_cycle', language_key='learning_memory_language')
TEXT = {
    'en': {'title': 'Learning Readiness Review',
           'caption': 'Read-only review of local raw snapshots. No training, memory replacement, GitHub publication or saved-weight changes.',
           'trust': 'Verification flags and source URLs are supplied claims, not authenticated proof. Existing saved weights remain unchanged and historically uncertified.',
           'coverage': 'Remote-only, session-only and SQLite-only records are outside this review. Every loaded original record and rejection reason is retained in the report.',
           'workspace': 'Workspace ID', 'run': 'Review local learning evidence',
           'blocked': 'Readiness blocked; no artifacts were written.',
           'ready': 'Structural readiness only; independent verification and offline validation remain required. No training occurred.',
           'download': 'Download observation-only review'},
    'es': {'title': 'Revisión de preparación del aprendizaje',
           'caption': 'Revisión de solo lectura de registros locales originales. Sin entrenamiento, reemplazo de memoria, publicación en GitHub ni cambios de pesos guardados.',
           'trust': 'Las marcas de verificación y URLs son afirmaciones proporcionadas, no pruebas autenticadas. Los pesos existentes siguen sin cambios y sin certificación histórica.',
           'coverage': 'Los registros exclusivos de remoto, sesión o SQLite quedan fuera de esta revisión. El reporte conserva cada registro original cargado y motivo de rechazo.',
           'workspace': 'ID del espacio de trabajo', 'run': 'Revisar evidencia local de aprendizaje',
           'blocked': 'Preparación bloqueada; no se escribió ningún archivo.',
           'ready': 'Solo preparación estructural; aún requiere verificación independiente y validación offline. No hubo entrenamiento.',
           'download': 'Descargar revisión de solo observación'},
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en'])[key]


st.title(t('title'))
st.info(t('caption'))
st.warning(t('trust'))
st.caption(t('coverage'))
workspace = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'))
if st.button(t('run'), type='primary', use_container_width=True):
    report = run_auto_learning_cycle(workspace, save_to_github=False)
    (st.warning if report['status'] == 'BLOCKED' else st.info)(t('blocked') if report['status'] == 'BLOCKED' else t('ready'))
    st.json(report)
    st.download_button(t('download'), json.dumps(report, indent=2, ensure_ascii=False),
                       file_name='learning_evidence_review.json', mime='application/json')

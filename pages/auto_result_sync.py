from __future__ import annotations

import json

import streamlit as st

from autonomous_betting_agent.auto_result_sync import run_auto_result_sync
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Auto Result Sync', layout='wide')
LANG = render_app_sidebar('auto_result_sync', language_key='learning_memory_language')

TEXT = {
    'en': {
        'title': 'Auto Result Sync',
        'caption': 'Finds completed scores, updates results and saves the ledger. The optional learning step only reviews local evidence; it does not train, write learning artifacts or change weights.',
        'workspace': 'Workspace ID',
        'days': 'Days back',
        'threshold': 'Match threshold',
        'key': 'Optional Odds API key override',
        'learn': 'Review learning evidence after result updates (no training)',
        'run': 'Find and update wins/losses now',
        'result': 'Sync result',
        'note': 'This uses Odds API completed scores by sport key. H2H is automatic. Spreads/totals are graded when team/line or over/under can be safely inferred; otherwise they are marked for review.',
    },
    'es': {
        'title': 'Sincronización Automática de Resultados',
        'caption': 'Busca marcadores finalizados, actualiza resultados y guarda el ledger. El paso opcional solo revisa evidencia local; no entrena, escribe archivos de aprendizaje ni cambia pesos.',
        'workspace': 'ID del espacio de trabajo',
        'days': 'Días atrás',
        'threshold': 'Umbral de coincidencia',
        'key': 'Clave Odds API opcional',
        'learn': 'Revisar evidencia tras actualizar resultados (sin entrenamiento)',
        'run': 'Buscar y actualizar ganadas/perdidas ahora',
        'result': 'Resultado de sincronización',
        'note': 'Usa marcadores finalizados de Odds API por sport key. H2H es automático. Spreads/totals se califican cuando equipo/línea u over/under se pueden inferir con seguridad.',
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))

workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

cols = st.columns(4)
days_from = cols[0].number_input(t('days'), min_value=1, max_value=7, value=3, step=1)
threshold = cols[1].number_input(t('threshold'), min_value=0.70, max_value=0.98, value=0.86, step=0.01)
run_learning = cols[2].toggle(t('learn'), value=True)
api_key = cols[3].text_input(t('key'), value='', type='password')

if st.button(t('run'), type='primary', use_container_width=True):
    try:
        report = run_auto_result_sync(
            workspace_id,
            api_key_override=api_key,
            days_from=int(days_from),
            threshold=float(threshold),
            run_learning_after=bool(run_learning),
        )
        st.subheader(t('result'))
        if report.get('status') == 'updated':
            st.success('Results updated.')
        elif report.get('status') == 'no_updates':
            st.warning('No rows were safely updated. Check needs_review details.')
        else:
            st.warning(f"Skipped: {report.get('reason')}")
        st.json(report)
        st.download_button('Download result sync report', json.dumps(report, indent=2, sort_keys=True), file_name='auto_result_sync_report.json', mime='application/json')
    except Exception as exc:
        st.error(str(exc))

from __future__ import annotations

import os

import streamlit as st

from autonomous_betting_agent.deployment_health_tools import (
    action_items,
    api_status_frame,
    deployment_summary,
    file_status_frame,
    ledger_status,
)

st.set_page_config(page_title='Deployment Health', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='deployment_health_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Deployment Health',
        'caption': 'No-login deployment diagnostics for integrations, pages, ledger, proof audit, and daily readiness.',
        'api': 'Integration status',
        'pages': 'Page/file status',
        'ledger': 'Persistent proof ledger',
        'actions': 'Action items',
        'score': 'Score',
        'status': 'Status',
        'locked': 'Locked rows',
        'quality': 'Proof quality',
        'review': 'Needs review',
        'note': 'This page checks whether runtime configuration exists, but it never displays private values.',
    },
    'es': {
        'title': 'Salud del Despliegue',
        'caption': 'Diagnóstico sin contraseña para integraciones, páginas, ledger, auditoría de prueba y preparación diaria.',
        'api': 'Estado de integraciones',
        'pages': 'Estado de páginas/archivos',
        'ledger': 'Ledger persistente de prueba',
        'actions': 'Acciones recomendadas',
        'score': 'Puntaje',
        'status': 'Estado',
        'locked': 'Filas bloqueadas',
        'quality': 'Calidad prueba',
        'review': 'Requiere revisión',
        'note': 'Esta página revisa si la configuración existe, pero nunca muestra valores privados.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def runtime_config_marker(name: str) -> str:
    try:
        value = str(st.secrets.get(name, '')).strip()
        if value:
            return 'configured_runtime_value_present_000'
    except Exception:
        pass
    value = os.getenv(name, '').strip()
    if value:
        return value
    return ''


summary = deployment_summary(runtime_config_marker)
ledger = ledger_status()

st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))
cols = st.columns(5)
cols[0].metric(t('score'), summary['deployment_score'])
cols[1].metric(t('status'), summary['deployment_status'])
cols[2].metric(t('locked'), ledger['locked_rows'])
cols[3].metric(t('quality'), ledger['proof_quality_score'])
cols[4].metric(t('review'), ledger['needs_review'])

st.subheader(t('actions'))
for item in action_items(summary):
    st.write(f'- {item}')

st.subheader(t('api'))
st.dataframe(api_status_frame(runtime_config_marker), use_container_width=True, hide_index=True)

st.subheader(t('pages'))
st.dataframe(file_status_frame(), use_container_width=True, hide_index=True)

st.subheader(t('ledger'))
st.json(ledger)

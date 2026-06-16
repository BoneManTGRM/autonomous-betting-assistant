from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.tool_sidebar import PAGE_GUIDES, WORKFLOW, proof_sidebar_snapshot, session_state_summary, render_tool_sidebar

st.set_page_config(page_title='Tool Command Center', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='tool_command_center_language') == 'Español' else 'en'
render_tool_sidebar('start_here', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Tool Command Center',
        'caption': 'Control panel for every sidebar tool: what each one does, when to use it, what it needs, what it creates, and the next step.',
        'tool_map': 'Sidebar tool map',
        'handoff': 'Current session handoff',
        'proof': 'Proof snapshot',
        'recommended': 'Recommended route',
        'selected': 'Selected tool deep guide',
        'tool': 'Tool',
        'purpose': 'Purpose',
        'use_when': 'Use when',
        'inputs': 'Inputs',
        'outputs': 'Outputs',
        'next': 'Next',
        'avoid': 'Avoid',
        'note': 'Use this page when you are not sure which sidebar tool to open next. It does not run APIs or change the ledger.',
    },
    'es': {
        'title': 'Centro de Comando de Herramientas',
        'caption': 'Panel para cada herramienta del sidebar: qué hace, cuándo usarla, qué necesita, qué crea y el siguiente paso.',
        'tool_map': 'Mapa de herramientas del sidebar',
        'handoff': 'Handoff actual de sesión',
        'proof': 'Resumen de prueba',
        'recommended': 'Ruta recomendada',
        'selected': 'Guía detallada de herramienta',
        'tool': 'Herramienta',
        'purpose': 'Propósito',
        'use_when': 'Úsala cuando',
        'inputs': 'Entradas',
        'outputs': 'Salidas',
        'next': 'Siguiente',
        'avoid': 'Evitar',
        'note': 'Usa esta página cuando no estás seguro qué herramienta abrir. No corre APIs ni cambia el ledger.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def page_rows() -> list[dict[str, str]]:
    rows = []
    for key, values in PAGE_GUIDES.items():
        guide = values.get(LANG, values['en'])
        rows.append({
            t('tool'): guide['name'],
            t('purpose'): guide['purpose'],
            t('use_when'): guide['use_when'],
            t('inputs'): guide['inputs'],
            t('outputs'): guide['outputs'],
            t('next'): guide['next'],
            t('avoid'): guide['avoid'],
        })
    return rows


def recommendation(snapshot: dict, session: pd.DataFrame) -> list[str]:
    locked = int(snapshot.get('locked_rows', 0) or 0)
    quality = float(snapshot.get('proof_quality', 0) or 0)
    session_counts = {row['session_key']: int(row['rows']) for row in session.to_dict(orient='records')}
    if locked == 0 and session_counts.get('what_are_the_odds_latest_rows', 0) > 0:
        return ['Open Odds Lock Pro', 'Create official future-only proof rows', 'Save locked rows to the persistent proof ledger']
    if locked == 0 and session_counts.get('pro_predictor_latest_rows', 0) > 0:
        return ['Open What Are the Odds', 'Review value/EV/manual context', 'Then move lock-ready rows to Odds Lock Pro']
    if locked == 0 and session_counts.get('scanner_pro_latest_rows', 0) > 0:
        return ['Open Pro Predictor', 'Create highest-confidence rows', 'Then review them in What Are the Odds']
    if locked == 0:
        return ['Open Deployment Health', 'Confirm API keys', 'Run Scanner Pro or Buyer Demo Mode']
    if locked < 25 or quality < 90:
        return ['Keep collecting future-only locks', 'Grade finished games in Auto Result Grading', 'Review proof quality in Public Proof Dashboard']
    return ['Open Monthly License Readiness', 'Review beta/operator readiness', 'Prepare private beta offer copy']


st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))

session = session_state_summary()
snapshot = proof_sidebar_snapshot()

cols = st.columns(5)
cols[0].metric('Locked proof rows' if LANG == 'en' else 'Filas prueba', snapshot['locked_rows'])
cols[1].metric('Resolved' if LANG == 'en' else 'Resueltos', snapshot['resolved_rows'])
cols[2].metric('Record' if LANG == 'en' else 'Récord', snapshot['record'])
cols[3].metric('Proof quality' if LANG == 'en' else 'Calidad prueba', snapshot['proof_quality'])
cols[4].metric('Needs review' if LANG == 'en' else 'Revisar', snapshot['needs_review'])

st.subheader(t('recommended'))
for item in recommendation(snapshot, session):
    st.write(f'- {item}')

left, right = st.columns([2, 1])
with left:
    st.subheader(t('tool_map'))
    st.dataframe(pd.DataFrame(page_rows()), use_container_width=True, hide_index=True)
with right:
    st.subheader(t('handoff'))
    st.dataframe(session, use_container_width=True, hide_index=True)
    st.subheader(t('proof'))
    st.json(snapshot)

st.subheader(t('selected'))
keys = list(PAGE_GUIDES.keys())
labels = [PAGE_GUIDES[key][LANG]['name'] if LANG in PAGE_GUIDES[key] else PAGE_GUIDES[key]['en']['name'] for key in keys]
choice = st.selectbox(t('tool'), labels)
selected_key = keys[labels.index(choice)]
guide = PAGE_GUIDES[selected_key].get(LANG, PAGE_GUIDES[selected_key]['en'])
st.markdown(f"### {guide['name']}")
st.write(f"**{t('purpose')}:** {guide['purpose']}")
st.write(f"**{t('use_when')}:** {guide['use_when']}")
st.write(f"**{t('inputs')}:** {guide['inputs']}")
st.write(f"**{t('outputs')}:** {guide['outputs']}")
st.write(f"**{t('next')}:** {guide['next']}")
st.warning(f"{t('avoid')}: {guide['avoid']}")
st.subheader('Workflow' if LANG == 'en' else 'Flujo')
st.dataframe(pd.DataFrame({'step': range(1, len(WORKFLOW) + 1), 'tool': WORKFLOW}), use_container_width=True, hide_index=True)

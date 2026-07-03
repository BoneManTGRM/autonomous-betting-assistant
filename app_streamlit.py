from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='ABA Signal Pro', layout='wide', initial_sidebar_state='expanded')
LANG = render_app_sidebar('home', language_key='global_language', selector='radio')

TEXT = {
    'en': {
        'title': 'ABA Signal Pro',
        'caption': 'Powered by Reparodynamics',
        'body': 'Use the Tools menu to run Pro Predictor, lock proof rows, grade results, and review learning memory.',
        'steps': 'Workflow: Pro Predictor → Odds Lock Pro → Proof Control Center → Public Proof Dashboard → Learning Memory.',
        'proof_control': 'Open Proof Control Center',
        'reset_storage': 'Open Reset Storage',
        'predictor': 'Open Pro Predictor',
    },
    'es': {
        'title': 'ABA Signal Pro',
        'caption': 'Impulsado por Reparodinámica',
        'body': 'Usa el menú de herramientas para ejecutar Predictor Pro, bloquear filas de prueba, calificar resultados y revisar la memoria de aprendizaje.',
        'steps': 'Flujo: Predictor Pro → Odds Lock Pro → Centro de control de pruebas → Panel público de pruebas → Memoria de aprendizaje.',
        'proof_control': 'Abrir Centro de control de pruebas',
        'reset_storage': 'Abrir restablecimiento de almacenamiento',
        'predictor': 'Abrir Predictor Pro',
    },
}

st.title(TEXT[LANG]['title'])
st.caption(TEXT[LANG]['caption'])
st.info(TEXT[LANG]['body'])
st.success(TEXT[LANG]['steps'])
st.page_link('pages/pro_predictor_volume.py', label=TEXT[LANG]['predictor'])
st.page_link('pages/proof_control_center.py', label=TEXT[LANG]['proof_control'])
st.page_link('pages/reset_storage.py', label=TEXT[LANG]['reset_storage'])
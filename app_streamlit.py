from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='ABA Signal Pro', layout='wide', initial_sidebar_state='expanded')
LANG = render_app_sidebar('home', language_key='global_language', selector='radio')

TEXT = {
    'en': {
        'title': 'ABA Signal Pro',
        'caption': 'Powered by Reparodynamics',
        'body': 'Use the Tools menu to run Pro Predictor, review odds, lock proof rows, and grade results.',
        'steps': 'Workflow: Pro Predictor → What Are the Odds → Odds Lock Pro → Proof Control Center → Public Proof Dashboard → Learning Memory.',
        'proof_control': 'Open Proof Control Center',
    },
    'es': {
        'title': 'ABA Signal Pro',
        'caption': 'Powered by Reparodynamics',
        'body': 'Usa el menú Tools para ejecutar Predictor Pro, revisar cuotas, bloquear pruebas y calificar resultados.',
        'steps': 'Flujo: Predictor Pro → What Are the Odds → Odds Lock Pro → Centro de Control de Prueba → Dashboard Público → Learning Memory.',
        'proof_control': 'Abrir Centro de Control de Prueba',
    },
}

st.title(TEXT[LANG]['title'])
st.caption(TEXT[LANG]['caption'])
st.info(TEXT[LANG]['body'])
st.success(TEXT[LANG]['steps'])
st.page_link('pages/proof_control_center.py', label=TEXT[LANG]['proof_control'])

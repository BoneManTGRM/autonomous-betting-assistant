from __future__ import annotations

import streamlit as st

PAGE_LANGUAGE_KEYS = [
    'deployment_health_language',
    'scanner_pro_language',
    'pro_predictor_language',
    'what_are_the_odds_pro_language',
    'odds_lock_pro_language',
    'public_proof_dashboard_language',
    'auto_result_grading_language',
    'daily_workflow_language',
    'learning_memory_language',
    'monthly_license_readiness_language',
    'buyer_demo_mode_language',
    'reset_data_language',
]

st.set_page_config(page_title='Language Settings', layout='wide')


def save_language(value: str) -> str:
    selected = 'Español' if str(value).lower().startswith('es') else 'English'
    st.session_state['global_language'] = selected
    st.session_state['app_language'] = selected
    for key in PAGE_LANGUAGE_KEYS:
        st.session_state[key] = selected
    try:
        st.query_params['lang'] = 'es' if selected == 'Español' else 'en'
    except Exception:
        pass
    return selected

current = st.session_state.get('global_language') or st.session_state.get('app_language') or 'English'
current = 'Español' if str(current).lower().startswith('es') else 'English'

st.title('Language Settings / Ajustes de Idioma')
st.caption('Choose once here. The app will keep this language across pages unless you change it again.')
st.caption('Elige una vez aquí. La app mantendrá este idioma entre páginas salvo que lo cambies otra vez.')

selected = st.radio('Language / Idioma', ['English', 'Español'], index=0 if current == 'English' else 1, horizontal=True)
if st.button('Save language / Guardar idioma', type='primary', use_container_width=True):
    saved = save_language(selected)
    if saved == 'Español':
        st.success('Idioma guardado. Cambia a otra página y debe mantenerse en Español.')
    else:
        st.success('Language saved. Change pages and it should remain in English.')

st.info(f'Current language / Idioma actual: {current}')
st.write('Stored keys / Claves guardadas:')
st.json({key: st.session_state.get(key) for key in ['global_language', 'app_language', *PAGE_LANGUAGE_KEYS]})

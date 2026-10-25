from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

TEXT = {
    'en': {
        'title': 'ABA Signal Pro',
        'caption': 'Powered by Reparodynamics',
        'body': 'Start with Pro Predictor, then use the Core section in the sidebar to review your work.',
        'steps': 'Workflow: Pro Predictor → Odds Lock Pro → Proof Center → Dashboard → Report Studio.',
        'local': 'No API key is needed to review saved records or use CSV/manual inputs in the local tools. Live data requires a configured provider and a successful request; opening this page does not fetch live data.',
        'advanced': 'Learning Memory and storage tools are under Show advanced tools in the sidebar.',
        'predictor': 'Open Pro Predictor',
    },
    'es': {
        'title': 'ABA Signal Pro',
        'caption': 'Impulsado por Reparodynamics',
        'body': 'Empieza con Predictor Pro y usa la sección Principal de la barra lateral para revisar tu trabajo.',
        'steps': 'Flujo: Predictor Pro → Odds Lock Pro → Centro de Prueba → Dashboard → Report Studio.',
        'local': 'No necesitas una clave API para revisar registros guardados o usar archivos CSV y entradas manuales en las herramientas locales. Los datos en vivo requieren un proveedor configurado y una consulta exitosa; abrir esta página no consulta datos en vivo.',
        'advanced': 'Memoria de Aprendizaje y las herramientas de almacenamiento están en Mostrar herramientas avanzadas, en la barra lateral.',
        'predictor': 'Abrir Predictor Pro',
    },
}

def render_home() -> None:
    """Render each Streamlit execution, independently of Python's module cache."""
    st.set_page_config(page_title='ABA Signal Pro', layout='wide', initial_sidebar_state='expanded')
    LANG = render_app_sidebar('home', language_key='global_language', selector='radio')
    st.title(TEXT[LANG]['title'])
    st.caption(TEXT[LANG]['caption'])
    st.info(TEXT[LANG]['body'])
    st.success(TEXT[LANG]['steps'])
    st.page_link('pages/pro_predictor_volume.py', label=TEXT[LANG]['predictor'])
    st.caption(TEXT[LANG]['local'])
    st.caption(TEXT[LANG]['advanced'])


if __name__ == '__main__':
    render_home()

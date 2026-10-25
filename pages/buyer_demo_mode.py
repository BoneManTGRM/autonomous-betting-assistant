from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    dashboard_metrics,
    demo_ledger,
    proof_audit_frame,
    public_dashboard_table,
    report_card_html,
    report_card_markdown,
)
from autonomous_betting_agent.daily_workflow_tools import workflow_stage_frame
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar

st.set_page_config(page_title='Buyer Demo Mode', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='buyer_demo_mode_language') == 'Español' else 'en'
render_tool_sidebar('buyer_demo_mode', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Buyer Demo Mode',
        'caption': 'A polished no-key demo that shows what the commercial platform looks like with locked proof rows.',
        'load': 'Load demo rows into session',
        'metrics': 'Demo metrics',
        'proof': 'Public proof table',
        'audit': 'Proof audit',
        'card': 'Buyer report card',
        'workflow': 'Demo workflow',
    },
    'es': {
        'title': 'Modo Demo para Comprador',
        'caption': 'Demo sin llave API que muestra cómo se ve la plataforma comercial con filas bloqueadas de prueba.',
        'load': 'Cargar filas demo en sesión',
        'metrics': 'Métricas demo',
        'proof': 'Tabla pública de prueba',
        'audit': 'Auditoría de prueba',
        'card': 'Tarjeta para comprador',
        'workflow': 'Flujo demo',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


demo = demo_ledger()
metrics = dashboard_metrics(demo)
st.title(t('title'))
st.caption(t('caption'))
if st.button(t('load'), type='primary', use_container_width=True):
    st.session_state['buyer_demo_mode_rows'] = demo.to_dict('records')
    st.success('Demo rows loaded.' if LANG == 'en' else 'Filas demo cargadas.')

cols = st.columns(6)
cols[0].metric('Locked', metrics['locked_picks'])
cols[1].metric('Resolved', metrics['resolved_picks'])
cols[2].metric('Record', f"{metrics['wins']}-{metrics['losses']}")
cols[3].metric('ROI', 'N/A' if metrics['roi'] is None else f"{metrics['roi'] * 100:.1f}%")
cols[4].metric('Avg CLV', 'N/A' if metrics['avg_clv_percent'] is None else f"{metrics['avg_clv_percent'] * 100:.2f}%")
cols[5].metric('Proof Quality', f"{metrics['proof_quality_score']}/100")

tabs = st.tabs([t('workflow'), t('proof'), t('audit'), t('card')])
with tabs[0]:
    st.dataframe(workflow_stage_frame({'input_rows': 12, 'candidate_rows': 5, 'locked_rows': len(demo), 'saved_rows': len(demo)}), use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(public_dashboard_table(demo), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(proof_audit_frame(demo), use_container_width=True, hide_index=True)
with tabs[3]:
    markdown = report_card_markdown(demo, title='Buyer Demo Proof Dashboard', brand='Demo Brand')
    html = report_card_html(demo, title='Buyer Demo Proof Dashboard', brand='Demo Brand')
    st.text_area('Markdown', value=markdown, height=240)
    st.markdown(html, unsafe_allow_html=True)
    st.text_area('HTML', value=html, height=260)

from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    demo_ledger,
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
)
from autonomous_betting_agent.monthly_license_tools import (
    client_package_frame,
    license_offer_text,
    next_build_queue,
    pricing_tiers_frame,
    readiness_checklist,
    readiness_scores,
)
from autonomous_betting_agent.commercial_platform_tools import dashboard_metrics
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar

st.set_page_config(page_title='Monthly License Readiness', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='monthly_license_readiness_language') == 'Español' else 'en'
render_tool_sidebar('monthly_license_readiness', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Monthly License Readiness',
        'caption': 'Buyer-facing readiness board for turning the agent into a monthly licensed analytics product.',
        'info': 'Use this page before pitching monthly clients. It checks proof strength, client safety, product pages, pricing tiers, and the next build queue. This is analytics/research software only; it does not guarantee wins or returns.',
        'use_db': 'Use persistent proof ledger',
        'use_session': 'Use current locked session rows',
        'use_demo': 'Use demo ledger if no real ledger exists',
        'upload': 'Upload locked proof ledger CSV',
        'source': 'Source',
        'brand': 'Brand name for offer text',
        'locked': 'Locked proof rows',
        'resolved': 'Resolved',
        'record': 'Record',
        'hit_rate': 'Hit rate',
        'roi': 'ROI',
        'beta': 'Beta readiness',
        'operator': 'Operator readiness',
        'checklist': 'Readiness checklist',
        'pricing': 'Pricing tiers',
        'package': 'Client package',
        'queue': 'Next build queue',
        'offer': 'Offer copy',
        'download_offer': 'Download offer text',
        'download_checklist': 'Download readiness checklist CSV',
        'no_rows': 'No locked proof rows found. Use demo mode to preview the sales board, but do not pitch real performance from demo rows.',
        'demo_warning': 'Demo mode is on. Use this only for product walkthroughs, not real proof claims.',
    },
    'es': {
        'title': 'Preparación Para Licencia Mensual',
        'caption': 'Panel para convertir el agente en un producto mensual de analítica con licencia.',
        'info': 'Usa esta página antes de presentar clientes mensuales. Revisa fuerza de prueba, seguridad para clientes, páginas del producto, precios y próximos pasos. Es software de analítica/investigación; no garantiza wins ni retornos.',
        'use_db': 'Usar ledger persistente de prueba',
        'use_session': 'Usar filas bloqueadas de la sesión actual',
        'use_demo': 'Usar ledger demo si no hay ledger real',
        'upload': 'Subir CSV de ledger bloqueado',
        'source': 'Fuente',
        'brand': 'Nombre de marca para la oferta',
        'locked': 'Filas bloqueadas',
        'resolved': 'Resueltos',
        'record': 'Récord',
        'hit_rate': 'Acierto',
        'roi': 'ROI',
        'beta': 'Preparación beta',
        'operator': 'Preparación operador',
        'checklist': 'Checklist de preparación',
        'pricing': 'Niveles de precio',
        'package': 'Paquete para cliente',
        'queue': 'Próximos pasos',
        'offer': 'Texto de oferta',
        'download_offer': 'Descargar texto de oferta',
        'download_checklist': 'Descargar checklist CSV',
        'no_rows': 'No se encontraron filas bloqueadas. Usa modo demo para ver el panel de venta, pero no presentes filas demo como prueba real.',
        'demo_warning': 'Modo demo activado. Úsalo solo para demostraciones del producto, no para claims de rendimiento real.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def read_sources() -> tuple[str, pd.DataFrame, bool]:
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    used_demo = False
    if st.checkbox(t('use_db'), value=True):
        db = load_persistent_ledger()
        if not db.empty:
            frames.append(db)
            names.append('persistent_ledger')
    if st.checkbox(t('use_session'), value=True):
        rows = st.session_state.get('odds_lock_pro_locked_rows') or []
        if rows:
            frame = pd.DataFrame(rows)
            frames.append(frame)
            names.append('session_locked_rows')
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                frames.append(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f'{upload.name}: {exc}')
    if not frames and st.checkbox(t('use_demo'), value=True):
        used_demo = True
        demo = demo_ledger()
        return 'demo_ledger', filter_locked_proof_rows(demo), used_demo
    if not frames:
        return '', pd.DataFrame(), used_demo
    return ', '.join(names), merge_ledgers(*frames), used_demo


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))

source, ledger, used_demo = read_sources()
st.caption(f"{t('source')}: {source or 'none'}")
if used_demo:
    st.warning(t('demo_warning'))
if ledger.empty:
    st.warning(t('no_rows'))
    st.stop()

brand = st.text_input(t('brand'), value='Private Analytics')
metrics = dashboard_metrics(ledger)
scores = readiness_scores(ledger)
checks = readiness_checklist(ledger)

cols = st.columns(8)
cols[0].metric(t('locked'), metrics['locked_picks'])
cols[1].metric(t('resolved'), metrics['resolved_picks'])
cols[2].metric(t('record'), f"{metrics['wins']}-{metrics['losses']}")
cols[3].metric(t('hit_rate'), pct(metrics['hit_rate']))
cols[4].metric(t('roi'), pct(metrics['roi']))
cols[5].metric('Proof quality', f"{metrics['proof_quality_score']}/100")
cols[6].metric(t('beta'), f"{scores['beta_score']}/100", scores['beta_status'])
cols[7].metric(t('operator'), f"{scores['operator_score']}/100", scores['operator_status'])

tabs = st.tabs([t('checklist'), t('pricing'), t('package'), t('queue'), t('offer')])

with tabs[0]:
    st.dataframe(checks, use_container_width=True, hide_index=True)
    st.download_button(t('download_checklist'), checks.to_csv(index=False), file_name='monthly_license_readiness_checklist.csv', mime='text/csv')

with tabs[1]:
    st.dataframe(pricing_tiers_frame(), use_container_width=True, hide_index=True)
    st.markdown(
        '**Recommended first move:** start with a 30-day private beta license at $500-$1,000/month, then raise pricing after 100+ future-locked proof rows.'
        if LANG == 'en'
        else '**Primer paso recomendado:** empieza con una beta privada de 30 días a $500-$1,000/mes, luego sube el precio después de 100+ filas futuras bloqueadas.'
    )

with tabs[2]:
    st.dataframe(client_package_frame(), use_container_width=True, hide_index=True)

with tabs[3]:
    queue = next_build_queue(checks)
    st.dataframe(queue, use_container_width=True, hide_index=True)

with tabs[4]:
    offer = license_offer_text(ledger, brand=brand)
    st.text_area(t('offer'), value=offer, height=420)
    st.download_button(t('download_offer'), offer, file_name='monthly_license_offer.txt', mime='text/plain')

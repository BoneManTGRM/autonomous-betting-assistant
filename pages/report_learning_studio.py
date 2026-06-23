from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.app_feed_delivery import save_app_feed
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.pdf_report import render_report_pdf
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.report_learning_layer import calibration_audit
from autonomous_betting_agent.report_learning_layer_compat import apply_learning_layer_compat as apply_learning_layer
from autonomous_betting_agent.report_product_layer import MagazineBrand, cards_to_json, enrich_rows, render_consumer_magazine_html, render_markdown_summary, safe_text
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck, render_status_dashboard
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.sports_context import CONTEXT_UNAVAILABLE, enrich_sports_context
from autonomous_betting_agent.white_label_profiles import WhiteLabelProfile, list_profiles, load_profile, save_profile

st.set_page_config(page_title='Learning Report Studio', layout='wide')
LANG = render_app_sidebar('report_learning_studio', language_key='report_studio_language', selector='radio')
T = {
    'en': {'title':'Learning Report Studio','caption':'Separates final result, price value, official +EV status, and calibration learning.','workspace':'Client / Workspace ID','saved':'Use saved workspace rows','upload':'Upload CSV rows','profile':'White-label profile','profile_id':'Profile ID','load':'Load','save':'Save','brand':'Brand / tipster name','tagline':'Tagline','report_title':'Report title','disclaimer':'Disclaimer','sports':'Sports / League Filter','max_rows':'Max rows','cards':'Premium Cards','mag':'Magazine Report','copy':'WhatsApp / Telegram','proof':'Analyst Proof','audit':'Calibration Audit','exports':'Exports','feed':'Saved app feed','pdf':'Download PDF','html':'Download HTML','md':'Download Markdown','json':'Download JSON','csv':'Download CSV','copy_download':'Download WhatsApp copy','empty':'No rows found. Use Pro Predictor / Odds Lock Pro first or upload a CSV.'},
    'es': {'title':'Estudio de aprendizaje','caption':'Separa resultado final, valor de precio, estado oficial +EV y aprendizaje de calibración.','workspace':'ID de cliente / workspace','saved':'Usar filas guardadas','upload':'Subir CSV','profile':'Perfil white-label','profile_id':'ID del perfil','load':'Cargar','save':'Guardar','brand':'Marca / tipster','tagline':'Lema','report_title':'Título del reporte','disclaimer':'Aviso legal','sports':'Filtro deporte / liga','max_rows':'Máximo de filas','cards':'Tarjetas premium','mag':'Reporte revista','copy':'WhatsApp / Telegram','proof':'Prueba técnica','audit':'Auditoría calibración','exports':'Exportaciones','feed':'Feed guardado','pdf':'Descargar PDF','html':'Descargar HTML','md':'Descargar Markdown','json':'Descargar JSON','csv':'Descargar CSV','copy_download':'Descargar copy WhatsApp','empty':'No hay filas. Usa Pro Predictor / Odds Lock Pro primero o sube un CSV.'},
}
HANDOFF_KEYS = ('odds_lock_pro_locked_rows','public_proof_dashboard_refresh_rows','pro_predictor_high_confidence_rows','pro_predictor_latest_rows','what_are_the_odds_latest_rows','ara_latest_predictions')

def t(k: str) -> str:
    return T.get(LANG, T['en']).get(k, k)

def saved_rows(workspace: str) -> pd.DataFrame:
    persistent = load_persistent_ledger(workspace_id=workspace, active_only=False)
    if persistent is not None and not persistent.empty:
        return persistent
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return pd.DataFrame(rows)
    _, rows = load_first_available(HANDOFF_KEYS, workspace)
    return pd.DataFrame(rows) if rows else pd.DataFrame()

def upload_rows() -> pd.DataFrame:
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    frames = []
    for upload in uploads or []:
        frame = pd.read_csv(upload)
        frame['source_file'] = upload.name
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()

def sport_options(frame: pd.DataFrame) -> list[str]:
    if frame.empty or 'sport' not in frame.columns:
        return []
    return sorted({safe_text(value) for value in frame['sport'].tolist() if safe_text(value)})

def copy_text(cards: pd.DataFrame, brand: MagazineBrand, limit: int = 8) -> str:
    es = LANG == 'es'
    rows = cards.head(limit).to_dict('records')
    lines = [brand.report_title, f'{brand.brand_name} — {brand.tagline}', '']
    for row in rows:
        lines.append(f"— {safe_text(row.get('event'))}: {safe_text(row.get('public_pick') or row.get('prediction'))}")
        lines.append(f"  {('Acción' if es else 'Action')}: {safe_text(row.get('consumer_action'))}")
        lines.append(f"  {('Resultado' if es else 'Result')}: {safe_text(row.get('result_status'))}")
        lines.append(f"  {('Aprendizaje' if es else 'Learning')}: {safe_text(row.get('learning_status'))}")
    if brand.disclaimer:
        lines += ['', brand.disclaimer]
    return '\n'.join(lines)

st.title(t('title'))
st.caption(t('caption'))
workspace = normalize_workspace_id(st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01')))
st.session_state['aba_test_window_id'] = workspace
use_saved = st.checkbox(t('saved'), value=True)
raw = pd.concat([df for df in (saved_rows(workspace) if use_saved else pd.DataFrame(), upload_rows()) if df is not None and not df.empty], ignore_index=True, sort=False) if True else pd.DataFrame()
if raw.empty:
    st.warning(t('empty'))
    st.stop()

normalized = normalize_frame(raw)
with st.expander(t('profile'), expanded=True):
    profile_ids = sorted({safe_text(row.get('profile_id')) for row in list_profiles() if safe_text(row.get('profile_id'))}) or ['default']
    p1, p2, p3 = st.columns([2, 1, 1])
    profile_id = p1.selectbox(t('profile_id'), profile_ids, index=0)
    if p2.button(t('load')):
        st.session_state['learning_profile'] = asdict(load_profile(profile_id)); st.rerun()
    loaded = WhiteLabelProfile(**st.session_state.get('learning_profile', {})).normalized() if st.session_state.get('learning_profile') else load_profile(profile_id)
    c1, c2 = st.columns(2)
    brand_name = c1.text_input(t('brand'), value=loaded.brand_name)
    tagline = c2.text_input(t('tagline'), value=loaded.tagline)
    report_title = c1.text_input(t('report_title'), value=loaded.report_title)
    disclaimer = st.text_area(t('disclaimer'), value=loaded.disclaimer, height=80)
    sports = st.multiselect(t('sports'), sport_options(normalized), default=[s for s in (loaded.preferred_sports or []) if s in sport_options(normalized)])
    if p3.button(t('save')):
        saved = save_profile(WhiteLabelProfile(profile_id=profile_id, workspace_id=workspace, brand_name=brand_name, tagline=tagline, language=LANG, report_title=report_title, disclaimer=disclaimer, preferred_sports=sports))
        st.session_state['learning_profile'] = asdict(saved)

max_rows = st.number_input(t('max_rows'), min_value=1, max_value=500, value=75, step=1)
filtered = normalized.copy()
if sports and 'sport' in filtered.columns:
    filtered = filtered[filtered['sport'].map(safe_text).isin(sports)].copy()
filtered = enrich_sports_context(filtered.head(int(max_rows)).copy(), language=LANG)
brand = MagazineBrand(brand_name=brand_name, tagline=tagline, report_title=report_title, workspace_id=workspace, language=LANG, disclaimer=disclaimer)
cards = apply_learning_layer(enrich_rows(filtered, language=LANG))
if 'sports_context_summary' in cards.columns:
    unavailable = CONTEXT_UNAVAILABLE.get(LANG, CONTEXT_UNAVAILABLE['en'])
    has_context = cards['sports_context_summary'].map(safe_text).ne('').astype(bool) & cards['sports_context_summary'].ne(unavailable)
    cards.loc[has_context, 'game_preview'] = cards.loc[has_context, 'sports_context_summary']

html_report = render_consumer_magazine_html(cards, brand)
md_report = render_markdown_summary(cards, brand)
wa = copy_text(cards, brand)
json_report = cards_to_json(cards)
pdf = render_report_pdf(cards, brand)
csv = cards.to_csv(index=False)
feed = save_app_feed(cards, brand, mode='consumer', public=False)
audit = calibration_audit(cards, min_sample=10)

st.markdown(render_status_dashboard(cards, language=LANG), unsafe_allow_html=True)
tabs = st.tabs([t('cards'), t('mag'), t('copy'), t('proof'), t('audit'), t('exports'), t('feed')])
with tabs[0]: st.markdown(render_premium_card_deck(cards, language=LANG), unsafe_allow_html=True)
with tabs[1]: st.markdown(html_report, unsafe_allow_html=True)
with tabs[2]: st.text_area(t('copy'), value=wa, height=420)
with tabs[3]:
    cols = [c for c in ['event','sport','prediction','model_lean_label','price_value_label','official_status_label','result_status','learning_status','official_publish_ready','client_report_ready','learning_ready','data_issue_reason','model_probability','market_probability','model_market_edge','expected_value_per_unit','profit_units'] if c in cards.columns]
    st.dataframe(cards[cols], use_container_width=True, hide_index=True)
with tabs[4]:
    for name, table in audit.items():
        st.subheader(name.replace('_', ' ').title())
        st.dataframe(table, use_container_width=True, hide_index=True)
with tabs[5]:
    safe_workspace = ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in workspace)
    st.download_button(t('pdf'), data=pdf, file_name=f'learning_report_{safe_workspace}.pdf', mime='application/pdf')
    st.download_button(t('html'), data=html_report, file_name=f'learning_report_{safe_workspace}.html', mime='text/html')
    st.download_button(t('md'), data=md_report, file_name=f'learning_report_{safe_workspace}.md', mime='text/markdown')
    st.download_button(t('copy_download'), data=wa, file_name=f'learning_copy_{safe_workspace}.txt', mime='text/plain')
    st.download_button(t('json'), data=json_report, file_name=f'learning_report_{safe_workspace}.json', mime='application/json')
    st.download_button(t('csv'), data=csv, file_name=f'learning_report_{safe_workspace}.csv', mime='text/csv')
with tabs[6]: st.json(feed)

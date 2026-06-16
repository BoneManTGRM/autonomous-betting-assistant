from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
    proof_audit_summary,
    save_persistent_ledger,
)
from autonomous_betting_agent.four_tool_orchestrator import page_health_frame
from autonomous_betting_agent.odds_lock_tools import (
    client_view,
    daily_report,
    exposure_summary,
    lock_rows,
    performance_by_group,
    prepare_lock_candidates,
    summarize_locked_picks,
    update_profit_columns,
)
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Odds Lock Pro', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='odds_lock_pro_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Odds Lock Pro','caption': 'Timestamped proof ledger, performance dashboard, reports, bankroll controls, and client-ready views.','info': 'Use this after What Are the Odds. Lock only future picks with usable probability, price, bookmaker, event start, and decision fields.','use_session': 'Use latest rows from session','upload': 'Upload prediction or locked-ledger CSV','source': 'Input source','analyst': 'Analyst / brand name','max_units': 'Max stake units per pick','daily_limit': 'Daily exposure limit','sport_limit': 'Per-sport exposure limit','include_watch': 'Include watch-only rows','lock': 'Create locked proof ledger','save_persistent': 'Save locked rows to persistent proof ledger','saved_persistent': 'Saved to persistent proof ledger','candidates': 'Lock candidates','locked': 'Locked proof ledger','dashboard': 'Proof dashboard','reports': 'Report generator','bankroll': 'Bankroll / exposure','client': 'Client view','rows': 'Rows','resolved': 'Resolved','record': 'Record','hit_rate': 'Hit rate','units': 'Units','roi': 'ROI','valid': 'Valid pre-start locks','proof_quality': 'Proof quality','download_locked': 'Download locked proof CSV','download_client': 'Download client-view CSV','download_private': 'Download private audit CSV','no_rows': 'No rows found. Run What Are the Odds first or upload a CSV.','no_locked': 'No locked proof rows yet. Create a locked proof ledger or upload a ledger with proof_id and locked_at_utc.','no_candidates': 'No lock candidates found. Use play_strong/play_small or lock_ready rows.','public_only': 'Public/client-safe view','report_language': 'Report language','report': 'Copy/paste report','handoff': 'Four-tool handoff health'},
    'es': {
        'title': 'Odds Lock Pro','caption': 'Ledger con prueba por timestamp, dashboard de rendimiento, reportes, control de unidades y vista para clientes.','info': 'Úsalo después de What Are the Odds. Bloquea solo picks futuros con probabilidad, cuota, casa, inicio del evento y decisión utilizables.','use_session': 'Usar últimas filas de la sesión','upload': 'Subir CSV de predicciones o ledger bloqueado','source': 'Fuente de entrada','analyst': 'Analista / marca','max_units': 'Máximo de unidades por pick','daily_limit': 'Límite diario de exposición','sport_limit': 'Límite de exposición por deporte','include_watch': 'Incluir filas solo vigilar','lock': 'Crear ledger de prueba bloqueada','save_persistent': 'Guardar filas bloqueadas en ledger persistente','saved_persistent': 'Guardado en ledger persistente','candidates': 'Candidatos para bloquear','locked': 'Ledger bloqueado','dashboard': 'Dashboard de prueba','reports': 'Generador de reportes','bankroll': 'Bankroll / exposición','client': 'Vista para clientes','rows': 'Filas','resolved': 'Resueltos','record': 'Récord','hit_rate': 'Tasa de acierto','units': 'Unidades','roi': 'ROI','valid': 'Bloqueos válidos antes del inicio','proof_quality': 'Calidad prueba','download_locked': 'Descargar CSV de prueba bloqueada','download_client': 'Descargar CSV para clientes','download_private': 'Descargar CSV privado de auditoría','no_rows': 'No se encontraron filas. Ejecuta What Are the Odds primero o sube un CSV.','no_locked': 'Aún no hay filas bloqueadas con prueba. Crea un ledger bloqueado o sube uno con proof_id y locked_at_utc.','no_candidates': 'No se encontraron candidatos. Usa filas play_strong/play_small o lock_ready.','public_only': 'Vista segura para público/clientes','report_language': 'Idioma del reporte','report': 'Reporte para copiar/pegar','handoff': 'Salud del traspaso entre herramientas'},
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def session_rows() -> tuple[str, list[dict]]:
    sources = [
        ('what_are_the_odds_latest_rows', 'What Are the Odds'),
        ('pro_predictor_latest_rows', 'Pro Predictor'),
        ('scanner_pro_latest_rows', 'Scanner Pro'),
        ('odds_lock_pro_locked_rows', 'Odds Lock Pro'),
        ('ara_latest_predictions', 'Latest session'),
    ]
    for key, label in sources:
        rows = st.session_state.get(key) or []
        if rows:
            return label, rows
    return '', []


def read_inputs() -> tuple[str, pd.DataFrame]:
    label, rows = session_rows()
    use_session = st.checkbox(t('use_session'), value=bool(rows))
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    if use_session and rows:
        frames.append(pd.DataFrame(rows))
        names.append(label or 'session_rows')
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
    if not frames:
        return '', pd.DataFrame()
    return ', '.join(names), pd.concat(frames, ignore_index=True, sort=False)


def has_proof_fields(frame: pd.DataFrame) -> bool:
    return not frame.empty and {'proof_id', 'locked_at_utc'}.issubset(set(frame.columns))


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))

source_name, raw = read_inputs()
st.caption(f"{t('source')}: {source_name or 'none'}")
if raw.empty:
    st.warning(t('no_rows'))
    st.stop()

normalized = normalize_frame(raw)
include_watch = st.checkbox(t('include_watch'), value=False)
analyst = st.text_input(t('analyst'), value='Private Analytics')
max_units = st.number_input(t('max_units'), min_value=0.25, max_value=10.0, value=2.0, step=0.25)
daily_limit = st.number_input(t('daily_limit'), min_value=0.25, max_value=100.0, value=5.0, step=0.25)
sport_limit = st.number_input(t('sport_limit'), min_value=0.25, max_value=100.0, value=3.0, step=0.25)

candidates = prepare_lock_candidates(normalized, include_watch=include_watch)
existing_locked = filter_locked_proof_rows(pd.DataFrame(st.session_state.get('odds_lock_pro_locked_rows', [])))
uploaded_locked = filter_locked_proof_rows(normalized) if has_proof_fields(normalized) else pd.DataFrame()

if st.button(t('lock'), type='primary', use_container_width=True):
    locked = lock_rows(normalized, analyst=analyst, max_units=float(max_units), include_watch=include_watch)
    st.session_state['odds_lock_pro_locked_rows'] = locked.to_dict('records')
    st.session_state['ara_latest_predictions'] = locked.to_dict('records')
    st.session_state['ara_latest_predictions_source'] = 'Odds Lock Pro'
    existing_locked = filter_locked_proof_rows(locked)

active_locked = existing_locked if not existing_locked.empty else uploaded_locked
summary = summarize_locked_picks(active_locked)
audit = proof_audit_summary(active_locked)
health_frame_source = active_locked if not active_locked.empty else candidates

cols = st.columns(8)
cols[0].metric(t('rows'), summary['locked_picks'])
cols[1].metric(t('resolved'), summary['resolved_picks'])
cols[2].metric(t('record'), f"{summary['wins']}-{summary['losses']}")
cols[3].metric(t('hit_rate'), pct(summary['hit_rate']))
cols[4].metric(t('units'), summary['profit_units'])
cols[5].metric(t('roi'), pct(summary['roi']))
cols[6].metric(t('valid'), summary['valid_before_start'])
cols[7].metric(t('proof_quality'), f"{audit['proof_quality_score']}/100")

st.subheader(t('handoff'))
st.dataframe(page_health_frame(health_frame_source, page='what_are_the_odds'), use_container_width=True, hide_index=True)

tabs = st.tabs([t('candidates'), t('locked'), t('dashboard'), t('reports'), t('bankroll'), t('client')])

with tabs[0]:
    if candidates.empty:
        st.warning(t('no_candidates'))
    else:
        show_cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price', 'bookmaker', 'agent_decision', 'agent_score', 'scanner_strength_score', 'model_edge', 'stake_units', 'prelock_status', 'public_confidence', 'public_reason'] if col in candidates.columns]
        st.dataframe(candidates[show_cols] if show_cols else candidates, use_container_width=True, hide_index=True)

with tabs[1]:
    if active_locked.empty:
        st.warning(t('no_locked'))
    else:
        st.dataframe(active_locked, use_container_width=True, hide_index=True)
        st.download_button(t('download_locked'), active_locked.to_csv(index=False), file_name='odds_lock_pro_locked_ledger.csv', mime='text/csv')
        if st.button(t('save_persistent'), use_container_width=True):
            combined = merge_ledgers(load_persistent_ledger(), active_locked)
            saved = save_persistent_ledger(combined)
            st.session_state['odds_lock_pro_locked_rows'] = saved.to_dict('records')
            st.success(f"{t('saved_persistent')}: {len(saved)} rows")

with tabs[2]:
    st.json({**summary, **audit})
    by_sport = performance_by_group(active_locked, 'sport')
    if not by_sport.empty:
        st.subheader('By sport' if LANG == 'en' else 'Por deporte')
        st.dataframe(by_sport, use_container_width=True, hide_index=True)
    by_market = performance_by_group(active_locked, 'market_type')
    if not by_market.empty:
        st.subheader('By market' if LANG == 'en' else 'Por mercado')
        st.dataframe(by_market, use_container_width=True, hide_index=True)

with tabs[3]:
    report_language = st.radio(t('report_language'), ['English', 'Español'], horizontal=True, index=0 if LANG == 'en' else 1)
    public_only = st.checkbox(t('public_only'), value=True, key='report_public_only')
    report_text = daily_report(active_locked, language=report_language, public_only=public_only)
    st.text_area(t('report'), value=report_text, height=360)

with tabs[4]:
    exposure = exposure_summary(active_locked, daily_limit_units=float(daily_limit), sport_limit_units=float(sport_limit))
    st.dataframe(exposure, use_container_width=True, hide_index=True)

with tabs[5]:
    public_only_client = st.checkbox(t('public_only'), value=True, key='client_public_only')
    client = client_view(active_locked, public_only=public_only_client)
    st.dataframe(client, use_container_width=True, hide_index=True)
    st.download_button(t('download_client') if public_only_client else t('download_private'), client.to_csv(index=False), file_name='odds_lock_pro_client_view.csv' if public_only_client else 'odds_lock_pro_private_audit.csv', mime='text/csv')

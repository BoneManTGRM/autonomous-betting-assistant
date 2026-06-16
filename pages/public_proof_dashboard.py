from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    apply_result_updates,
    dashboard_metrics,
    daily_locked_report,
    demo_ledger,
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
    proof_audit_frame,
    proof_audit_summary,
    public_dashboard_table,
    report_card_html,
    report_card_markdown,
    save_persistent_ledger,
)
from autonomous_betting_agent.odds_lock_tools import performance_by_group, update_profit_columns
from autonomous_betting_agent.row_normalizer import normalize_frame, safe_text

st.set_page_config(page_title='Public Proof Dashboard', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='public_proof_dashboard_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Public Proof Dashboard',
        'caption': 'No-login proof dashboard for locked picks, auto-grading uploads, client-safe tables, shareable report cards, and historical tracker review.',
        'info': 'Official proof mode uses locked proof rows with proof_id and locked_at_utc. Historical tracker mode can display older result CSVs, but those rows are clearly marked non-proof and do not count as official future-locked proof.',
        'use_demo': 'Use demo ledger when no real ledger exists',
        'use_db': 'Use persistent ledger database',
        'use_session': 'Use Odds Lock Pro session rows',
        'upload_ledger': 'Upload locked ledger or historical tracker CSV',
        'upload_results': 'Upload finished results CSV for auto-grading',
        'save_db': 'Save merged ledger to persistent CSV database',
        'apply_results': 'Apply result updates',
        'source': 'Source',
        'rows': 'Locked',
        'resolved': 'Resolved',
        'record': 'Record',
        'hit_rate': 'Hit rate',
        'roi': 'ROI',
        'units': 'Units',
        'pending': 'Pending',
        'clv': 'Avg CLV',
        'proof_quality': 'Proof quality',
        'valid': 'Valid proof rows',
        'filtered': 'Filtered rows',
        'filters': 'Dashboard filters',
        'sport_filter': 'Sport filter',
        'market_filter': 'Market filter',
        'status_filter': 'Result status filter',
        'table': 'Public ledger table',
        'dashboard': 'Breakdowns',
        'audit': 'Proof audit',
        'cards': 'Report cards',
        'markdown_card': 'Markdown card',
        'html_card': 'HTML card',
        'daily_report': 'Daily report',
        'brand': 'Brand name',
        'card_title': 'Card title',
        'download_public': 'Download public proof CSV',
        'download_private': 'Download private audit CSV',
        'download_audit': 'Download proof audit CSV',
        'download_markdown': 'Download Markdown card',
        'download_html': 'Download HTML card',
        'download_report': 'Download daily report TXT',
        'download_tracker': 'Download normalized tracker CSV',
        'no_rows': 'No proof rows or historical tracker rows found yet. Create locks in Odds Lock Pro or upload a CSV.',
        'updated': 'Result update summary',
        'safety': 'Proof safety check',
        'tracker_mode': 'Historical tracker mode — not official proof',
        'tracker_warning': 'This file can be reviewed for record tracking, but it is not official proof because it lacks proof_id and locked_at_utc. Use Odds Lock Pro before games start for official monthly-license proof.',
        'ignored_nonproof': 'Ignored raw/non-proof rows',
    },
    'es': {
        'title': 'Dashboard Público de Prueba',
        'caption': 'Dashboard sin contraseña para picks bloqueados, autocalificación por CSV, tablas para clientes, tarjetas compartibles y revisión histórica.',
        'info': 'El modo de prueba oficial usa filas bloqueadas con proof_id y locked_at_utc. El modo histórico puede mostrar CSVs viejos de resultados, pero se marcan como no-prueba y no cuentan como prueba oficial futura.',
        'use_demo': 'Usar ledger demo si no hay ledger real',
        'use_db': 'Usar base CSV persistente',
        'use_session': 'Usar filas de Odds Lock Pro en sesión',
        'upload_ledger': 'Subir CSV de ledger bloqueado o tracker histórico',
        'upload_results': 'Subir CSV de resultados finalizados para autocalificar',
        'save_db': 'Guardar ledger combinado en base CSV persistente',
        'apply_results': 'Aplicar resultados',
        'source': 'Fuente',
        'rows': 'Bloqueados',
        'resolved': 'Resueltos',
        'record': 'Récord',
        'hit_rate': 'Acierto',
        'roi': 'ROI',
        'units': 'Unidades',
        'pending': 'Pendientes',
        'clv': 'CLV prom.',
        'proof_quality': 'Calidad prueba',
        'valid': 'Filas de prueba válidas',
        'filtered': 'Filas filtradas',
        'filters': 'Filtros del dashboard',
        'sport_filter': 'Filtro de deporte',
        'market_filter': 'Filtro de mercado',
        'status_filter': 'Filtro de resultado',
        'table': 'Tabla pública del ledger',
        'dashboard': 'Desgloses',
        'audit': 'Auditoría de prueba',
        'cards': 'Tarjetas de reporte',
        'markdown_card': 'Tarjeta Markdown',
        'html_card': 'Tarjeta HTML',
        'daily_report': 'Reporte diario',
        'brand': 'Nombre de marca',
        'card_title': 'Título de tarjeta',
        'download_public': 'Descargar CSV público',
        'download_private': 'Descargar CSV privado',
        'download_audit': 'Descargar CSV de auditoría',
        'download_markdown': 'Descargar tarjeta Markdown',
        'download_html': 'Descargar tarjeta HTML',
        'download_report': 'Descargar reporte diario TXT',
        'download_tracker': 'Descargar tracker normalizado CSV',
        'no_rows': 'No se encontraron filas de prueba ni tracker histórico. Crea bloqueos en Odds Lock Pro o sube un CSV.',
        'updated': 'Resumen de actualización de resultados',
        'safety': 'Chequeo de seguridad de prueba',
        'tracker_mode': 'Modo tracker histórico — no es prueba oficial',
        'tracker_warning': 'Este archivo sirve para revisar récord, pero no es prueba oficial porque no tiene proof_id ni locked_at_utc. Usa Odds Lock Pro antes del inicio para prueba oficial mensual.',
        'ignored_nonproof': 'Filas crudas/no-prueba ignoradas',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: float | None, digits: int = 1) -> str:
    return 'N/A' if value is None else f'{value * 100:.{digits}f}%'


def read_sources() -> tuple[str, pd.DataFrame, pd.DataFrame, int]:
    raw_frames: list[pd.DataFrame] = []
    ledger_frames: list[pd.DataFrame] = []
    raw_count = 0
    names: list[str] = []
    if st.checkbox(t('use_db'), value=True):
        db = load_persistent_ledger()
        if not db.empty:
            raw_frames.append(db)
            ledger_frames.append(db)
            raw_count += len(db)
            names.append('persistent_ledger')
    if st.checkbox(t('use_session'), value=True):
        rows = st.session_state.get('odds_lock_pro_locked_rows') or []
        if rows:
            session_frame = pd.DataFrame(rows)
            raw_frames.append(session_frame)
            ledger_frames.append(session_frame)
            raw_count += len(session_frame)
            names.append('session_locked_rows')
    uploads = st.file_uploader(t('upload_ledger'), type=['csv'], accept_multiple_files=True)
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                raw_frames.append(frame)
                locked = filter_locked_proof_rows(frame)
                if not locked.empty:
                    ledger_frames.append(locked)
                raw_count += len(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f'{upload.name}: {exc}')
    if not raw_frames:
        if st.checkbox(t('use_demo'), value=True):
            demo = demo_ledger()
            return 'demo_ledger', demo, demo, len(demo)
        return '', pd.DataFrame(), pd.DataFrame(), 0
    raw_all = pd.concat(raw_frames, ignore_index=True, sort=False)
    ledger = merge_ledgers(*ledger_frames) if ledger_frames else pd.DataFrame()
    return ', '.join(names), ledger, raw_all, raw_count


def filter_dashboard(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    with st.expander(t('filters'), expanded=False):
        filtered = frame.copy()
        sport_options = sorted([str(value) for value in filtered.get('sport', pd.Series(dtype=str)).dropna().unique() if str(value).strip()])
        market_options = sorted([str(value) for value in filtered.get('market_type', pd.Series(dtype=str)).dropna().unique() if str(value).strip()])
        status_options = sorted([str(value) for value in filtered.get('result_status', pd.Series(dtype=str)).dropna().unique() if str(value).strip()])
        selected_sports = st.multiselect(t('sport_filter'), sport_options, default=sport_options)
        selected_markets = st.multiselect(t('market_filter'), market_options, default=market_options)
        selected_statuses = st.multiselect(t('status_filter'), status_options, default=status_options)
        if selected_sports and 'sport' in filtered.columns:
            filtered = filtered[filtered['sport'].astype(str).isin(selected_sports)]
        if selected_markets and 'market_type' in filtered.columns:
            filtered = filtered[filtered['market_type'].astype(str).isin(selected_markets)]
        if selected_statuses and 'result_status' in filtered.columns:
            filtered = filtered[filtered['result_status'].astype(str).isin(selected_statuses)]
        st.caption(f"{t('filtered')}: {len(filtered)}")
        return filtered


def tracker_metrics(frame: pd.DataFrame) -> dict[str, int | float | None]:
    normalized = normalize_frame(frame)
    if normalized.empty:
        return {'rows': 0, 'resolved': 0, 'wins': 0, 'losses': 0, 'pending': 0, 'hit_rate': None}
    status = normalized.get('result_status', pd.Series(dtype=str)).astype(str).str.lower()
    wins = int(status.eq('win').sum())
    losses = int(status.eq('loss').sum())
    resolved = wins + losses
    pending = int(status.isin(['pending', 'unknown', 'scheduled', 'live', '']).sum())
    return {'rows': int(len(normalized)), 'resolved': resolved, 'wins': wins, 'losses': losses, 'pending': pending, 'hit_rate': None if resolved == 0 else round(wins / resolved, 6)}


def show_tracker_mode(frame: pd.DataFrame) -> None:
    normalized = normalize_frame(frame)
    if normalized.empty:
        st.warning(t('no_rows'))
        st.stop()
    metrics = tracker_metrics(normalized)
    st.warning(t('tracker_warning'))
    cols = st.columns(6)
    cols[0].metric('Rows' if LANG == 'en' else 'Filas', metrics['rows'])
    cols[1].metric(t('resolved'), metrics['resolved'])
    cols[2].metric(t('record'), f"{metrics['wins']}-{metrics['losses']}")
    cols[3].metric(t('hit_rate'), pct(metrics['hit_rate']))
    cols[4].metric(t('pending'), metrics['pending'])
    cols[5].metric(t('proof_quality'), '0/100')
    st.subheader(t('tracker_mode'))
    show_cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'result_status', 'winner', 'final_score', 'event_start_utc', 'source_file'] if col in normalized.columns]
    st.dataframe(normalized[show_cols] if show_cols else normalized, use_container_width=True, hide_index=True)
    st.download_button(t('download_tracker'), normalized.to_csv(index=False), file_name='historical_tracker_non_proof.csv', mime='text/csv')
    st.stop()


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))

source, ledger, raw_input, raw_count = read_sources()
st.caption(f"{t('source')}: {source or 'none'}")

results_upload = st.file_uploader(t('upload_results'), type=['csv'], accept_multiple_files=False, key='proof_results_upload')
if results_upload is not None and not ledger.empty:
    try:
        result_frame = pd.read_csv(results_upload)
        if st.button(t('apply_results'), type='primary', use_container_width=True):
            ledger, update_stats = apply_result_updates(ledger, result_frame)
            st.session_state['odds_lock_pro_locked_rows'] = ledger.to_dict('records')
            st.json({t('updated'): update_stats})
    except Exception as exc:
        st.warning(str(exc))

if not ledger.empty and source != 'demo_ledger' and st.button(t('save_db'), use_container_width=True):
    ledger = save_persistent_ledger(ledger)
    st.success('Saved persistent ledger.' if LANG == 'en' else 'Ledger persistente guardado.')

ledger = filter_locked_proof_rows(ledger)
if ledger.empty:
    if not raw_input.empty:
        show_tracker_mode(raw_input)
    st.warning(t('no_rows'))
    st.stop()

ledger = update_profit_columns(ledger)
filtered_ledger = filter_dashboard(ledger)
metrics = dashboard_metrics(filtered_ledger)
audit_summary = proof_audit_summary(filtered_ledger)
raw_cols = st.columns(3)
raw_cols[0].metric(t('valid'), len(ledger))
raw_cols[1].metric(t('ignored_nonproof'), max(0, raw_count - len(ledger)))
raw_cols[2].metric(t('proof_quality'), f"{audit_summary['proof_quality_score']}/100")

cols = st.columns(9)
cols[0].metric(t('rows'), metrics['locked_picks'])
cols[1].metric(t('resolved'), metrics['resolved_picks'])
cols[2].metric(t('record'), f"{metrics['wins']}-{metrics['losses']}")
cols[3].metric(t('hit_rate'), pct(metrics['hit_rate']))
cols[4].metric(t('roi'), pct(metrics['roi']))
cols[5].metric(t('units'), metrics['profit_units'])
cols[6].metric(t('pending'), metrics['pending_picks'])
cols[7].metric(t('clv'), pct(metrics.get('avg_clv_percent'), 2))
cols[8].metric('Beat close' if LANG == 'en' else 'Superó cierre', pct(metrics.get('beat_close_rate')))

tabs = st.tabs([t('table'), t('dashboard'), t('audit'), t('cards')])

with tabs[0]:
    public = public_dashboard_table(filtered_ledger)
    st.dataframe(public, use_container_width=True, hide_index=True)
    st.download_button(t('download_public'), public.to_csv(index=False), file_name='public_proof_dashboard.csv', mime='text/csv')
    st.download_button(t('download_private'), filtered_ledger.to_csv(index=False), file_name='private_proof_audit.csv', mime='text/csv')

with tabs[1]:
    st.json(metrics)
    by_sport = performance_by_group(filtered_ledger, 'sport')
    if not by_sport.empty:
        st.subheader('By sport' if LANG == 'en' else 'Por deporte')
        st.dataframe(by_sport, use_container_width=True, hide_index=True)
    by_market = performance_by_group(filtered_ledger, 'market_type')
    if not by_market.empty:
        st.subheader('By market' if LANG == 'en' else 'Por mercado')
        st.dataframe(by_market, use_container_width=True, hide_index=True)

with tabs[2]:
    st.json(audit_summary)
    audit = proof_audit_frame(filtered_ledger)
    st.dataframe(audit, use_container_width=True, hide_index=True)
    st.download_button(t('download_audit'), audit.to_csv(index=False), file_name='proof_audit.csv', mime='text/csv')

with tabs[3]:
    brand = st.text_input(t('brand'), value='Private Analytics')
    title = st.text_input(t('card_title'), value='Proof Dashboard')
    markdown = report_card_markdown(filtered_ledger, title=title, brand=brand)
    html = report_card_html(filtered_ledger, title=title, brand=brand)
    report = daily_locked_report(filtered_ledger, language='Español' if LANG == 'es' else 'English')
    st.subheader(t('markdown_card'))
    st.text_area(t('markdown_card'), value=markdown, height=240)
    st.download_button(t('download_markdown'), markdown, file_name='proof_dashboard_card.md', mime='text/markdown')
    st.subheader(t('html_card'))
    st.markdown(html, unsafe_allow_html=True)
    st.text_area(t('html_card'), value=html, height=280)
    st.download_button(t('download_html'), html, file_name='proof_dashboard_card.html', mime='text/html')
    st.subheader(t('daily_report'))
    st.text_area(t('daily_report'), value=report, height=340)
    st.download_button(t('download_report'), report, file_name='daily_locked_report.txt', mime='text/plain')

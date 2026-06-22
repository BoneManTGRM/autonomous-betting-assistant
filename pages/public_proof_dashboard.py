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
    normalize_workspace_id,
    proof_audit_frame,
    proof_audit_summary,
    public_dashboard_table,
    report_card_html,
    report_card_markdown,
    save_persistent_ledger,
)
from autonomous_betting_agent.odds_lock_tools import performance_by_group, update_profit_columns
from autonomous_betting_agent.pick_hold_store import load_first_available, save_held_rows
from autonomous_betting_agent.row_normalizer import normalize_frame, safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Public Proof Dashboard', layout='wide')
LANG = render_app_sidebar('public_proof_dashboard', language_key='public_proof_dashboard_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Public Proof Dashboard',
        'caption': 'Client-safe proof dashboard for locked picks, result uploads, report cards, and historical tracker review.',
        'info': 'Official proof mode uses rows locked before start with proof_id and locked_at_utc. Historical tracker rows can be reviewed, but they are not official proof.',
        'test_window': 'Test Window ID',
        'active_test_window': 'Active test ledger',
        'use_db': 'Use full saved database',
        'use_session': 'Use current synced dashboard rows',
        'use_demo': 'Show demo ledger if no real ledger exists',
        'upload_ledger': 'Upload locked ledger or historical tracker CSV',
        'upload_results': 'Upload finished results CSV for auto-grading',
        'save_db': 'Save current dashboard ledger to this test ledger',
        'apply_results': 'Apply result updates',
        'source': 'Source',
        'active_source': 'Active proof source',
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
        'ignored_nonproof': 'Ignored raw/non-proof rows',
        'filtered': 'Filtered rows',
        'filters': 'Dashboard filters',
        'sport_filter': 'Sport filter',
        'market_filter': 'Market filter',
        'status_filter': 'Result status filter',
        'table': 'Public ledger table',
        'dashboard': 'Breakdowns',
        'audit': 'Proof audit',
        'cards': 'Report cards',
        'brand': 'Brand name',
        'card_title': 'Card title',
        'markdown_card': 'Markdown card',
        'html_card': 'HTML card',
        'daily_report': 'Daily report',
        'download_public': 'Download public proof CSV',
        'download_private': 'Download private audit CSV',
        'download_audit': 'Download proof audit CSV',
        'download_markdown': 'Download Markdown card',
        'download_html': 'Download HTML card',
        'download_report': 'Download daily report TXT',
        'download_tracker': 'Download normalized tracker CSV',
        'no_rows': 'No current proof rows loaded. Run Pro Predictor Volume, upload the locked CSV, or intentionally enable full saved database.',
        'updated': 'Result update summary',
        'tracker_mode': 'Historical tracker mode — not official proof',
        'tracker_warning': 'This file can be reviewed for record tracking, but it is not official proof because it lacks proof_id and locked_at_utc. Use Pro Predictor Volume/Odds Lock Pro before games start for official proof.',
    },
    'es': {
        'title': 'Dashboard Público de Prueba',
        'caption': 'Dashboard para clientes con picks bloqueados, carga de resultados, tarjetas y revisión histórica.',
        'info': 'El modo oficial usa filas bloqueadas antes del inicio con proof_id y locked_at_utc.',
        'test_window': 'ID de ventana de prueba',
        'active_test_window': 'Ledger activo',
        'use_db': 'Usar base guardada completa',
        'use_session': 'Usar filas sincronizadas actuales',
        'use_demo': 'Mostrar demo',
        'upload_ledger': 'Subir CSV bloqueado o tracker histórico',
        'upload_results': 'Subir CSV de resultados',
        'save_db': 'Guardar ledger actual',
        'apply_results': 'Aplicar resultados',
        'source': 'Fuente',
        'active_source': 'Fuente activa',
        'rows': 'Bloqueados',
        'resolved': 'Resueltos',
        'record': 'Récord',
        'hit_rate': 'Acierto',
        'roi': 'ROI',
        'units': 'Unidades',
        'pending': 'Pendientes',
        'clv': 'CLV prom.',
        'proof_quality': 'Calidad prueba',
        'valid': 'Filas válidas',
        'ignored_nonproof': 'Filas ignoradas/no-prueba',
        'filtered': 'Filas filtradas',
        'filters': 'Filtros',
        'sport_filter': 'Deporte',
        'market_filter': 'Mercado',
        'status_filter': 'Estado',
        'table': 'Tabla pública',
        'dashboard': 'Desgloses',
        'audit': 'Auditoría',
        'cards': 'Tarjetas',
        'brand': 'Marca',
        'card_title': 'Título',
        'markdown_card': 'Markdown',
        'html_card': 'HTML',
        'daily_report': 'Reporte',
        'download_public': 'Descargar CSV público',
        'download_private': 'Descargar CSV privado',
        'download_audit': 'Descargar auditoría',
        'download_markdown': 'Descargar Markdown',
        'download_html': 'Descargar HTML',
        'download_report': 'Descargar reporte TXT',
        'download_tracker': 'Descargar tracker',
        'no_rows': 'No hay filas actuales.',
        'updated': 'Actualización',
        'tracker_mode': 'Tracker histórico — no prueba oficial',
        'tracker_warning': 'Este archivo no es prueba oficial porque no tiene proof_id y locked_at_utc.',
    },
}

SESSION_KEYS = ['public_proof_dashboard_refresh_rows', 'odds_lock_pro_locked_rows']


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: float | None, digits: int = 1) -> str:
    return 'N/A' if value is None else f'{value * 100:.{digits}f}%'


def load_saved_session_rows(workspace_id: str) -> tuple[str, pd.DataFrame]:
    for key in SESSION_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return key, pd.DataFrame(rows)
    key, rows = load_first_available(SESSION_KEYS, workspace_id)
    if rows:
        st.session_state[key] = rows
        return f'local:{key}', pd.DataFrame(rows)
    return '', pd.DataFrame()


def read_sources(workspace_id: str, *, use_db: bool, use_session: bool, use_demo: bool, uploads: list | None) -> tuple[str, pd.DataFrame, pd.DataFrame, int]:
    raw_frames: list[pd.DataFrame] = []
    ledger_frames: list[pd.DataFrame] = []
    raw_count = 0
    names: list[str] = []
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
    if use_session:
        label, session_frame = load_saved_session_rows(workspace_id)
        if not session_frame.empty:
            raw_frames.append(session_frame)
            locked = filter_locked_proof_rows(session_frame)
            if not locked.empty:
                ledger_frames.append(locked)
            raw_count += len(session_frame)
            names.append(label)
    if use_db:
        db = load_persistent_ledger(workspace_id=workspace_id)
        if not db.empty:
            raw_frames.append(db)
            ledger_frames.append(db)
            raw_count += len(db)
            names.append(f'persistent_ledger:{workspace_id}')
    if not raw_frames:
        if use_demo:
            demo = demo_ledger()
            return 'demo_ledger', demo, demo, len(demo)
        return '', pd.DataFrame(), pd.DataFrame(), 0
    raw_all = pd.concat(raw_frames, ignore_index=True, sort=False)
    ledger = merge_ledgers(*ledger_frames) if ledger_frames else pd.DataFrame()
    return ', '.join(names), ledger, raw_all, raw_count


def active_source_summary(frame: pd.DataFrame, source: str, workspace_id: str) -> dict[str, str | int]:
    if frame.empty:
        return {'source': source or 'none', 'workspace_id': workspace_id, 'rows': 0}
    def unique_text(col: str) -> str:
        if col not in frame.columns:
            return ''
        values = [safe_text(v) for v in frame[col].dropna().unique() if safe_text(v)]
        if not values:
            return ''
        return values[0] if len(values) == 1 else f'{values[0]} (+{len(values)-1} more)'
    status = frame.get('result_status', pd.Series(dtype=str)).astype(str).str.lower()
    locked = pd.to_datetime(frame.get('locked_at_utc', pd.Series(dtype=str)), errors='coerce', utc=True)
    starts = pd.to_datetime(frame.get('event_start_utc', pd.Series(dtype=str)), errors='coerce', utc=True)
    return {
        'source': source or 'none',
        'workspace_id': workspace_id,
        'source_file': unique_text('source_file'),
        'active_list_id': unique_text('active_list_id'),
        'ledger_batch_id': unique_text('ledger_batch_id'),
        'rows': int(len(frame)),
        'wins': int(status.eq('win').sum()),
        'losses': int(status.eq('loss').sum()),
        'voids': int(status.isin(['void', 'push', 'cancelled', 'canceled']).sum()),
        'pending': int(status.isin(['', 'pending', 'unknown', 'scheduled', 'live', 'needs_review']).sum()),
        'locked_at_min': '' if locked.dropna().empty else locked.min().isoformat(),
        'locked_at_max': '' if locked.dropna().empty else locked.max().isoformat(),
        'event_start_min': '' if starts.dropna().empty else starts.min().isoformat(),
        'event_start_max': '' if starts.dropna().empty else starts.max().isoformat(),
    }


def show_source_summary(frame: pd.DataFrame, source: str, workspace_id: str) -> None:
    info = active_source_summary(frame, source, workspace_id)
    st.subheader(t('active_source'))
    c = st.columns(5)
    c[0].metric('Rows', info.get('rows', 0))
    c[1].metric('Wins', info.get('wins', 0))
    c[2].metric('Losses', info.get('losses', 0))
    c[3].metric('Voids', info.get('voids', 0))
    c[4].metric('Pending', info.get('pending', 0))
    with st.expander('Active source identity', expanded=True):
        st.json(info)


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
    cols[0].metric('Rows', metrics['rows'])
    cols[1].metric(t('resolved'), metrics['resolved'])
    cols[2].metric(t('record'), f"{metrics['wins']}-{metrics['losses']}")
    cols[3].metric(t('hit_rate'), pct(metrics['hit_rate']))
    cols[4].metric(t('pending'), metrics['pending'])
    cols[5].metric(t('proof_quality'), '0/100')
    show_cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'result_status', 'winner', 'final_score', 'event_start_utc', 'source_file'] if col in normalized.columns]
    st.dataframe(normalized[show_cols] if show_cols else normalized, use_container_width=True, hide_index=True)
    st.download_button(t('download_tracker'), normalized.to_csv(index=False), file_name='historical_tracker_non_proof.csv', mime='text/csv')
    st.stop()


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))
st.caption('The active source box below shows exactly which file/list is being counted. Raw predictor CSVs without proof_id are shown as tracker rows, not official proof.')

with st.expander(t('active_test_window'), expanded=True):
    workspace_input = st.text_input(t('test_window'), value=st.session_state.get('aba_test_window_id', 'test_01'))
    use_db = st.checkbox(t('use_db'), value=False, help='OFF by default so historical rows do not silently replace the active list.')
    use_session = st.checkbox(t('use_session'), value=True, help='ON by default so the dashboard shows the current list synced by Pro Predictor Volume / Full Auto Update.')
    use_demo = st.checkbox(t('use_demo'), value=False, key='public_proof_use_demo')
    uploads = st.file_uploader(t('upload_ledger'), type=['csv'], accept_multiple_files=True)

workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id
source, ledger, raw_input, raw_count = read_sources(workspace_id, use_db=use_db, use_session=use_session, use_demo=use_demo, uploads=uploads)
st.caption(f"{t('active_test_window')}: {workspace_id}")
st.caption(f"{t('source')}: {source or 'none'}")

results_upload = st.file_uploader(t('upload_results'), type=['csv'], accept_multiple_files=False, key='proof_results_upload')
if results_upload is not None and not ledger.empty:
    try:
        result_frame = pd.read_csv(results_upload)
        if st.button(t('apply_results'), type='primary', use_container_width=True):
            ledger, update_stats = apply_result_updates(ledger, result_frame)
            ledger['test_window_id'] = workspace_id
            records = ledger.to_dict('records')
            st.session_state['odds_lock_pro_locked_rows'] = records
            st.session_state['public_proof_dashboard_refresh_rows'] = records
            save_held_rows('odds_lock_pro_locked_rows', records, workspace_id)
            save_held_rows('public_proof_dashboard_refresh_rows', records, workspace_id)
            save_persistent_ledger(ledger, workspace_id=workspace_id)
            st.json({t('updated'): update_stats})
    except Exception as exc:
        st.warning(str(exc))

if not ledger.empty and source != 'demo_ledger' and st.button(t('save_db'), use_container_width=True):
    ledger['test_window_id'] = workspace_id
    ledger = save_persistent_ledger(ledger, workspace_id=workspace_id)
    records = ledger.to_dict('records')
    save_held_rows('odds_lock_pro_locked_rows', records, workspace_id)
    save_held_rows('public_proof_dashboard_refresh_rows', records, workspace_id)
    st.success(('Saved persistent ledger: ' if LANG == 'en' else 'Ledger persistente guardado: ') + workspace_id)

ledger = filter_locked_proof_rows(ledger)
if ledger.empty:
    if not raw_input.empty:
        show_tracker_mode(raw_input)
    st.warning(t('no_rows'))
    st.stop()

ledger = update_profit_columns(ledger)
show_source_summary(ledger, source, workspace_id)
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
    st.download_button(t('download_public'), public.to_csv(index=False), file_name=f'public_proof_dashboard_{workspace_id}.csv', mime='text/csv')
    st.download_button(t('download_private'), filtered_ledger.to_csv(index=False), file_name=f'private_proof_audit_{workspace_id}.csv', mime='text/csv')
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
    st.download_button(t('download_audit'), audit.to_csv(index=False), file_name=f'proof_audit_{workspace_id}.csv', mime='text/csv')
with tabs[3]:
    brand = st.text_input(t('brand'), value='ABA Signal Pro · Powered by Reparodynamics')
    title = st.text_input(t('card_title'), value='Proof Dashboard')
    markdown = report_card_markdown(filtered_ledger, title=title, brand=brand)
    html = report_card_html(filtered_ledger, title=title, brand=brand)
    report = daily_locked_report(filtered_ledger, language='Español' if LANG == 'es' else 'English')
    st.text_area(t('markdown_card'), value=markdown, height=240)
    st.download_button(t('download_markdown'), markdown, file_name=f'proof_dashboard_card_{workspace_id}.md', mime='text/markdown')
    st.markdown(html, unsafe_allow_html=True)
    st.text_area(t('html_card'), value=html, height=280)
    st.download_button(t('download_html'), html, file_name=f'proof_dashboard_card_{workspace_id}.html', mime='text/html')
    st.text_area(t('daily_report'), value=report, height=340)
    st.download_button(t('download_report'), report, file_name=f'daily_locked_report_{workspace_id}.txt', mime='text/plain')

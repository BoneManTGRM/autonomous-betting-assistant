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
from autonomous_betting_agent.event_exposure import add_event_exposure_columns, exposure_metrics
from autonomous_betting_agent.odds_lock_tools import performance_by_group, update_profit_columns
from autonomous_betting_agent.pick_hold_store import load_first_available, save_held_rows
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options, localize_value, render_upload_css

SESSION_KEYS = ['public_proof_dashboard_refresh_rows', 'odds_lock_pro_locked_rows']
IDENTITY_COLUMNS = ['active_list_id', 'ledger_batch_id', 'source_file']

TEXT = {
    'en': {
        'title': 'Public Proof Dashboard', 'caption': 'Client-safe proof dashboard for locked picks, result uploads, report cards, and historical tracker review.',
        'info': 'Official proof mode uses rows locked before start with proof_id and locked_at_utc. Historical tracker rows can be reviewed, but they are not official proof.',
        'active_test_window': 'Active test ledger', 'test_window': 'Test Window ID', 'use_db': 'Use full saved database', 'use_session': 'Use current synced dashboard rows', 'use_demo': 'Show demo ledger if no real ledger exists',
        'upload_ledger': 'Upload locked ledger or historical tracker CSV', 'upload_results': 'Upload finished results CSV for auto-grading', 'save_db': 'Save current dashboard ledger to this test ledger', 'apply_results': 'Apply result updates',
        'source': 'Source', 'active_source': 'Active proof source', 'valid': 'Valid proof rows', 'ignored_nonproof': 'Ignored raw/non-proof rows', 'proof_quality': 'Proof quality',
        'events': 'Unique events', 'pick_rows': 'Pick rows', 'completed_events': 'Completed events', 'resolved': 'Resolved picks', 'record': 'Record', 'hit_rate': 'Hit rate', 'voids': 'Voids', 'pending': 'Pending',
        'wins': 'Wins', 'losses': 'Losses', 'multi_market': 'Multi-market events', 'extra_pick_rows': 'Extra same-event rows', 'roi': 'ROI', 'units': 'Units', 'clv': 'Avg CLV', 'beat_close': 'Beat close',
        'filters': 'Dashboard filters', 'filtered': 'Filtered rows', 'sport_filter': 'Sport filter', 'market_filter': 'Market filter', 'status_filter': 'Result status filter',
        'table': 'Public ledger table', 'dashboard': 'Breakdowns', 'audit': 'Proof audit', 'cards': 'Report cards', 'brand': 'Brand name', 'card_title': 'Card title',
        'markdown_card': 'Markdown card', 'html_card': 'HTML card', 'daily_report': 'Daily report', 'download_public': 'Download public proof CSV', 'download_private': 'Download private audit CSV', 'download_audit': 'Download proof audit CSV',
        'download_markdown': 'Download Markdown card', 'download_html': 'Download HTML card', 'download_report': 'Download daily report TXT', 'download_tracker': 'Download normalized tracker CSV',
        'no_rows': 'No current proof rows loaded. Run Pro Predictor Volume after this redeploy, upload the current locked CSV, or intentionally enable full saved database.',
        'tracker_warning': 'This file can be reviewed for record tracking, but it is not official proof because it lacks proof_id and locked_at_utc.', 'updated': 'Result update summary',
        'stale_warning': 'Ignored stale synced dashboard rows with no source_file/active_list_id. Run Pro Predictor Volume again or enable full saved database intentionally.',
        'source_identity': 'Active source identity', 'by_sport': 'By sport', 'by_market': 'By market', 'saved': 'Saved persistent ledger: ',
    },
    'es': {
        'title': 'Dashboard Público de Prueba', 'caption': 'Dashboard para clientes con picks bloqueados.', 'info': 'El modo oficial usa filas bloqueadas antes del inicio con proof_id y locked_at_utc.',
        'active_test_window': 'Ledger activo', 'test_window': 'ID de ventana', 'use_db': 'Usar base completa', 'use_session': 'Usar filas sincronizadas actuales', 'use_demo': 'Mostrar demo',
        'upload_ledger': 'Subir CSV', 'upload_results': 'Subir resultados', 'save_db': 'Guardar ledger actual', 'apply_results': 'Aplicar resultados', 'source': 'Fuente', 'active_source': 'Fuente activa',
        'valid': 'Filas válidas', 'ignored_nonproof': 'Ignoradas/no-prueba', 'proof_quality': 'Calidad prueba', 'events': 'Eventos únicos', 'pick_rows': 'Filas de picks', 'completed_events': 'Eventos terminados',
        'resolved': 'Picks resueltos', 'record': 'Récord', 'hit_rate': 'Acierto', 'voids': 'Voids', 'pending': 'Pendientes', 'wins': 'Victorias', 'losses': 'Derrotas', 'multi_market': 'Eventos multi-mercado', 'extra_pick_rows': 'Filas extra mismo evento',
        'roi': 'ROI', 'units': 'Unidades', 'clv': 'CLV prom.', 'beat_close': 'Superó cierre', 'filters': 'Filtros', 'filtered': 'Filas filtradas', 'sport_filter': 'Deporte', 'market_filter': 'Mercado', 'status_filter': 'Estado',
        'table': 'Tabla pública', 'dashboard': 'Desgloses', 'audit': 'Auditoría', 'cards': 'Tarjetas', 'brand': 'Marca', 'card_title': 'Título', 'markdown_card': 'Markdown', 'html_card': 'HTML',
        'daily_report': 'Reporte', 'download_public': 'Descargar público', 'download_private': 'Descargar privado', 'download_audit': 'Descargar auditoría', 'download_markdown': 'Descargar Markdown', 'download_html': 'Descargar HTML',
        'download_report': 'Descargar reporte', 'download_tracker': 'Descargar tracker', 'no_rows': 'No hay filas actuales.', 'tracker_warning': 'Este archivo no es prueba oficial porque no tiene proof_id y locked_at_utc.', 'updated': 'Actualización',
        'stale_warning': 'Se ignoraron filas sincronizadas antiguas sin source_file/active_list_id. Ejecuta Pro Predictor Volume otra vez o activa la base completa intencionalmente.',
        'source_identity': 'Identidad de fuente activa', 'by_sport': 'Por deporte', 'by_market': 'Por mercado', 'saved': 'Ledger persistente guardado: ',
    },
}


def _t(lang: str, key: str) -> str:
    return TEXT[lang].get(key, TEXT['en'].get(key, key))


def _pct(value: float | None, digits: int = 1) -> str:
    return 'N/A' if value is None else f'{value * 100:.{digits}f}%'


def _has_current_identity(frame: pd.DataFrame) -> bool:
    locked = filter_locked_proof_rows(frame)
    if locked.empty:
        return False
    return any(col in locked.columns and locked[col].map(safe_text).ne('').any() for col in IDENTITY_COLUMNS)


def _load_saved_session_rows(workspace_id: str, lang: str) -> tuple[str, pd.DataFrame]:
    skipped = []
    for key in SESSION_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            frame = pd.DataFrame(rows)
            if _has_current_identity(frame):
                return key, frame
            skipped.append(key)
    for key in SESSION_KEYS:
        loaded_key, rows = load_first_available([key], workspace_id)
        if rows:
            frame = pd.DataFrame(rows)
            if _has_current_identity(frame):
                st.session_state[key] = rows
                return f'local:{key}', frame
            skipped.append(f'local:{key}')
    if skipped:
        st.warning(_t(lang, 'stale_warning'))
    return '', pd.DataFrame()


def _read_sources(workspace_id: str, *, use_db: bool, use_session: bool, use_demo: bool, uploads: list | None, lang: str) -> tuple[str, pd.DataFrame, pd.DataFrame, int]:
    raw_frames, ledger_frames, names = [], [], []
    raw_count = 0
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
        label, session_frame = _load_saved_session_rows(workspace_id, lang)
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
        demo = demo_ledger() if use_demo else pd.DataFrame()
        return ('demo_ledger' if use_demo else ''), demo, demo, len(demo)
    raw_all = pd.concat(raw_frames, ignore_index=True, sort=False)
    ledger = merge_ledgers(*ledger_frames) if ledger_frames else pd.DataFrame()
    return ', '.join(names), ledger, raw_all, raw_count


def _with_metrics(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    exposed = add_event_exposure_columns(frame)
    metrics = dashboard_metrics(exposed) if not exposed.empty else {}
    metrics.update(exposure_metrics(exposed))
    return exposed, metrics


def _filter_dashboard(frame: pd.DataFrame, lang: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    with st.expander(_t(lang, 'filters'), expanded=False):
        filtered = frame.copy()
        for col, label in [('sport', 'sport_filter'), ('market_type', 'market_filter'), ('result_status', 'status_filter')]:
            if col not in filtered.columns:
                continue
            options = sorted([str(v) for v in filtered[col].dropna().unique() if str(v).strip()])
            display_options, display_to_raw = localize_options(options, lang)
            selected_display = st.multiselect(_t(lang, label), display_options, default=display_options)
            selected = [display_to_raw.get(item, item) for item in selected_display]
            if selected:
                filtered = filtered[filtered[col].astype(str).isin(selected)]
        st.caption(f"{_t(lang, 'filtered')}: {len(filtered)}")
        return filtered


def _show_source_summary(frame: pd.DataFrame, source: str, workspace_id: str, lang: str) -> None:
    exposed = add_event_exposure_columns(frame)
    metrics = exposure_metrics(exposed)
    status = exposed.get('result_status', pd.Series(dtype=str)).astype(str).str.lower() if not exposed.empty else pd.Series(dtype=str)
    info = {
        'source': source or 'none', 'workspace_id': workspace_id,
        'pick_rows': metrics['pick_rows'], 'unique_events': metrics['unique_events'], 'completed_events': metrics['completed_events'],
        'wins': int(status.eq('win').sum()), 'losses': int(status.eq('loss').sum()), 'voids': metrics['voids'], 'pending': metrics['pending_pick_rows'],
        'events_with_multiple_pick_rows': metrics['events_with_multiple_pick_rows'], 'extra_same_event_pick_rows': metrics['extra_same_event_pick_rows'],
        'max_pick_rows_per_event': metrics['max_pick_rows_per_event'],
    }
    st.subheader(_t(lang, 'active_source'))
    cols = st.columns(7)
    cols[0].metric(_t(lang, 'events'), info['unique_events']); cols[1].metric(_t(lang, 'pick_rows'), info['pick_rows']); cols[2].metric(_t(lang, 'wins'), info['wins']); cols[3].metric(_t(lang, 'losses'), info['losses']); cols[4].metric(_t(lang, 'voids'), info['voids']); cols[5].metric(_t(lang, 'pending'), info['pending']); cols[6].metric(_t(lang, 'multi_market'), info['events_with_multiple_pick_rows'])
    with st.expander(_t(lang, 'source_identity'), expanded=True):
        st.dataframe(localize_dataframe(pd.DataFrame([info]), lang), use_container_width=True, hide_index=True)


def _show_tracker_mode(raw_input: pd.DataFrame, lang: str) -> None:
    exposed, metrics = _with_metrics(raw_input)
    if exposed.empty:
        st.warning(_t(lang, 'no_rows'))
        st.stop()
    st.warning(_t(lang, 'tracker_warning'))
    cols = st.columns(8)
    cols[0].metric(_t(lang, 'events'), metrics['unique_events']); cols[1].metric(_t(lang, 'pick_rows'), metrics['pick_rows']); cols[2].metric(_t(lang, 'completed_events'), metrics['completed_events']); cols[3].metric(_t(lang, 'record'), f"{metrics['wins']}-{metrics['losses']}"); cols[4].metric(_t(lang, 'hit_rate'), _pct(metrics['pick_hit_rate_excluding_voids'])); cols[5].metric(_t(lang, 'voids'), metrics['voids']); cols[6].metric(_t(lang, 'pending'), metrics['pending_pick_rows']); cols[7].metric(_t(lang, 'proof_quality'), '0/100')
    st.caption(f"{_t(lang, 'multi_market')}: {metrics['events_with_multiple_pick_rows']} | {_t(lang, 'extra_pick_rows')}: {metrics['extra_same_event_pick_rows']}")
    show_cols = [col for col in ['event', 'unique_event_id', 'same_event_pick_count', 'event_pick_index', 'sport', 'market_type', 'line_point', 'prediction', 'result_status', 'winner', 'final_score', 'event_start_utc', 'source_file'] if col in exposed.columns]
    st.dataframe(localize_dataframe(exposed[show_cols] if show_cols else exposed, lang), use_container_width=True, hide_index=True)
    st.download_button(_t(lang, 'download_tracker'), exposed.to_csv(index=False), file_name='historical_tracker_non_proof.csv', mime='text/csv')
    st.stop()


def _public_table_with_exposure(frame: pd.DataFrame) -> pd.DataFrame:
    public = public_dashboard_table(frame)
    if public.empty or len(public) != len(frame):
        return public
    out = public.copy()
    insert_at = 1 if 'event' in out.columns else 0
    for col in ['unique_event_id', 'same_event_pick_count', 'event_pick_index']:
        if col in frame.columns and col not in out.columns:
            out.insert(min(insert_at, len(out.columns)), col, frame[col].to_list())
            insert_at += 1
    return out


def run() -> None:
    st.set_page_config(page_title='Public Proof Dashboard', layout='wide')
    lang = render_app_sidebar('public_proof_dashboard', language_key='public_proof_dashboard_language', selector='radio')
    render_upload_css(st, lang)
    st.title(_t(lang, 'title'))
    st.caption(_t(lang, 'caption'))
    st.info(_t(lang, 'info'))
    st.caption('Current synced rows must include source_file, active_list_id, or ledger_batch_id. Stale old rows without identity are ignored.' if lang == 'en' else 'Las filas sincronizadas deben incluir source_file, active_list_id o ledger_batch_id. Las filas antiguas sin identidad se ignoran.')

    with st.expander(_t(lang, 'active_test_window'), expanded=True):
        workspace_input = st.text_input(_t(lang, 'test_window'), value=st.session_state.get('aba_test_window_id', 'test_01'))
        use_db = st.checkbox(_t(lang, 'use_db'), value=False, help='OFF by default so historical rows do not silently replace the active list.' if lang == 'en' else 'Apagado por defecto para que filas históricas no reemplacen la lista activa.')
        use_session = st.checkbox(_t(lang, 'use_session'), value=True, help='ON by default for current synced rows only. Stale rows without source identity are ignored.' if lang == 'en' else 'Encendido por defecto solo para filas sincronizadas actuales. Las filas antiguas sin identidad se ignoran.')
        use_demo = st.checkbox(_t(lang, 'use_demo'), value=False, key='public_proof_use_demo')
        uploads = st.file_uploader(_t(lang, 'upload_ledger'), type=['csv'], accept_multiple_files=True)

    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state['aba_test_window_id'] = workspace_id
    source, ledger, raw_input, raw_count = _read_sources(workspace_id, use_db=use_db, use_session=use_session, use_demo=use_demo, uploads=uploads, lang=lang)
    st.caption(f"{_t(lang, 'active_test_window')}: {workspace_id}")
    st.caption(f"{_t(lang, 'source')}: {localize_value(source or 'none', lang)}")

    results_upload = st.file_uploader(_t(lang, 'upload_results'), type=['csv'], accept_multiple_files=False, key='proof_results_upload')
    if results_upload is not None and not ledger.empty:
        result_frame = pd.read_csv(results_upload)
        if st.button(_t(lang, 'apply_results'), type='primary', use_container_width=True):
            ledger, update_stats = apply_result_updates(ledger, result_frame)
            ledger['test_window_id'] = workspace_id
            records = ledger.to_dict('records')
            st.session_state['odds_lock_pro_locked_rows'] = records
            st.session_state['public_proof_dashboard_refresh_rows'] = records
            save_held_rows('odds_lock_pro_locked_rows', records, workspace_id)
            save_held_rows('public_proof_dashboard_refresh_rows', records, workspace_id)
            save_persistent_ledger(ledger, workspace_id=workspace_id)
            st.json({_t(lang, 'updated'): update_stats})

    if not ledger.empty and source != 'demo_ledger' and st.button(_t(lang, 'save_db'), use_container_width=True):
        ledger['test_window_id'] = workspace_id
        ledger = save_persistent_ledger(ledger, workspace_id=workspace_id)
        records = ledger.to_dict('records')
        save_held_rows('odds_lock_pro_locked_rows', records, workspace_id)
        save_held_rows('public_proof_dashboard_refresh_rows', records, workspace_id)
        st.success(_t(lang, 'saved') + workspace_id)

    ledger = filter_locked_proof_rows(ledger)
    if ledger.empty:
        if not raw_input.empty:
            _show_tracker_mode(raw_input, lang)
        st.warning(_t(lang, 'no_rows'))
        st.stop()

    ledger, _ = _with_metrics(update_profit_columns(ledger))
    _show_source_summary(ledger, source, workspace_id, lang)
    filtered_ledger = _filter_dashboard(ledger, lang)
    filtered_ledger, metrics = _with_metrics(filtered_ledger)
    audit_summary = proof_audit_summary(filtered_ledger)

    raw_cols = st.columns(5)
    raw_cols[0].metric(_t(lang, 'valid'), len(ledger)); raw_cols[1].metric(_t(lang, 'events'), metrics['unique_events']); raw_cols[2].metric(_t(lang, 'ignored_nonproof'), max(0, raw_count - len(ledger))); raw_cols[3].metric(_t(lang, 'multi_market'), metrics['events_with_multiple_pick_rows']); raw_cols[4].metric(_t(lang, 'proof_quality'), f"{audit_summary['proof_quality_score']}/100")
    cols = st.columns(10)
    cols[0].metric(_t(lang, 'events'), metrics['unique_events']); cols[1].metric(_t(lang, 'pick_rows'), metrics['pick_rows']); cols[2].metric(_t(lang, 'completed_events'), metrics['completed_events']); cols[3].metric(_t(lang, 'resolved'), metrics['resolved_pick_rows']); cols[4].metric(_t(lang, 'record'), f"{metrics['wins']}-{metrics['losses']}"); cols[5].metric(_t(lang, 'hit_rate'), _pct(metrics['pick_hit_rate_excluding_voids'])); cols[6].metric(_t(lang, 'roi'), _pct(metrics.get('roi'))); cols[7].metric(_t(lang, 'units'), metrics.get('profit_units', 0)); cols[8].metric(_t(lang, 'pending'), metrics['pending_pick_rows']); cols[9].metric(_t(lang, 'clv'), _pct(metrics.get('avg_clv_percent'), 2))
    st.caption(f"{_t(lang, 'voids')}: {metrics['voids']} | {_t(lang, 'extra_pick_rows')}: {metrics['extra_same_event_pick_rows']} | {_t(lang, 'beat_close')}: {_pct(metrics.get('beat_close_rate'))}")

    tabs = st.tabs([_t(lang, 'table'), _t(lang, 'dashboard'), _t(lang, 'audit'), _t(lang, 'cards')])
    with tabs[0]:
        public = _public_table_with_exposure(filtered_ledger)
        st.dataframe(localize_dataframe(public, lang), use_container_width=True, hide_index=True)
        st.download_button(_t(lang, 'download_public'), public.to_csv(index=False), file_name=f'public_proof_dashboard_{workspace_id}.csv', mime='text/csv')
        st.download_button(_t(lang, 'download_private'), filtered_ledger.to_csv(index=False), file_name=f'private_proof_audit_{workspace_id}.csv', mime='text/csv')
    with tabs[1]:
        st.dataframe(localize_dataframe(pd.DataFrame([metrics]), lang), use_container_width=True, hide_index=True)
        by_sport = performance_by_group(filtered_ledger, 'sport')
        if not by_sport.empty:
            st.subheader(_t(lang, 'by_sport')); st.dataframe(localize_dataframe(by_sport, lang), use_container_width=True, hide_index=True)
        by_market = performance_by_group(filtered_ledger, 'market_type')
        if not by_market.empty:
            st.subheader(_t(lang, 'by_market')); st.dataframe(localize_dataframe(by_market, lang), use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(localize_dataframe(pd.DataFrame([audit_summary]), lang), use_container_width=True, hide_index=True)
        audit = proof_audit_frame(filtered_ledger)
        st.dataframe(localize_dataframe(audit, lang), use_container_width=True, hide_index=True)
        st.download_button(_t(lang, 'download_audit'), audit.to_csv(index=False), file_name=f'proof_audit_{workspace_id}.csv', mime='text/csv')
    with tabs[3]:
        brand = st.text_input(_t(lang, 'brand'), value='ABA Signal Pro · Powered by Reparodynamics')
        title = st.text_input(_t(lang, 'card_title'), value='Proof Dashboard' if lang == 'en' else 'Dashboard de Prueba')
        markdown = report_card_markdown(filtered_ledger, title=title, brand=brand)
        html = report_card_html(filtered_ledger, title=title, brand=brand)
        report = daily_locked_report(filtered_ledger, language='Español' if lang == 'es' else 'English')
        st.text_area(_t(lang, 'markdown_card'), value=markdown, height=240); st.download_button(_t(lang, 'download_markdown'), markdown, file_name=f'proof_dashboard_card_{workspace_id}.md', mime='text/markdown')
        st.markdown(html, unsafe_allow_html=True); st.text_area(_t(lang, 'html_card'), value=html, height=280); st.download_button(_t(lang, 'download_html'), html, file_name=f'proof_dashboard_card_{workspace_id}.html', mime='text/html')
        st.text_area(_t(lang, 'daily_report'), value=report, height=340); st.download_button(_t(lang, 'download_report'), report, file_name=f'daily_locked_report_{workspace_id}.txt', mime='text/plain')

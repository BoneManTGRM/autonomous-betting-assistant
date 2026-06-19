from __future__ import annotations

import base64
import html
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import (
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
    normalize_workspace_id,
    proof_audit_summary,
    save_persistent_ledger,
)
from autonomous_betting_agent.four_tool_orchestrator import page_health_frame
from autonomous_betting_agent.odds_lock_tools import (
    client_view,
    daily_report,
    lock_rows,
    lock_status,
    now_utc,
    parse_datetime_utc,
    performance_by_group,
    prepare_lock_candidates,
    profit_units,
    proof_hash,
    proof_id_from_hash,
    summarize_locked_picks,
)
from autonomous_betting_agent.pick_hold_store import load_first_available, save_held_rows
from autonomous_betting_agent.row_normalizer import normalize_frame, safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Odds Lock Pro', layout='wide')
LANG = render_app_sidebar('odds_lock_pro', language_key='odds_lock_pro_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Odds Lock Pro',
        'caption': 'Create timestamped research/test locks and persistent proof ledgers.',
        'info': 'Use this page to lock rows before games start. Public Proof Dashboard reads the saved proof ledger.',
        'test_window': 'Test Window ID',
        'test_window_help': 'Use the same ID in Public Proof Dashboard, such as test_01.',
        'input': 'Input',
        'use_session': 'Use latest saved/session rows',
        'upload': 'Upload prediction or locked-ledger CSV',
        'source': 'Input source',
        'include_watch': 'Include watch/tracker rows',
        'analyst': 'Analyst / brand name',
        'max_units': 'Max stake units per pick',
        'shortlist': 'Highest-confidence shortlist',
        'use_shortlist': 'Use shortlist',
        'max_shortlist': 'Max shortlist rows',
        'min_shortlist_prob': 'Minimum model probability',
        'min_shortlist_score': 'Minimum agent score',
        'lock_research': 'Create research/test future-only ledger',
        'lock': 'Create official +EV future-only ledger',
        'research_lock_created': 'Created and saved research/test locked rows',
        'lock_created': 'Created and saved official +EV locked rows',
        'research_lock_not_created': 'No research/test ledger was created.',
        'lock_not_created': 'No official +EV ledger was created.',
        'no_rows': 'No rows found. Run Pro Predictor first or upload a CSV.',
        'no_locked': 'No locked proof rows yet.',
        'locked': 'Locked proof ledger',
        'research_candidates_tab': 'Research/Test candidates',
        'official_candidates_tab': 'Official +EV candidates',
        'dashboard': 'Proof dashboard',
        'reports': 'Report generator',
        'client': 'Client view',
        'input_rows': 'Input rows',
        'persistent_rows': 'Saved ledger',
        'reviewed': 'Reviewed',
        'research_candidates': 'Research/Test',
        'official_candidates': 'Official +EV',
        'rows': 'Rows',
        'resolved': 'Resolved',
        'record': 'Record',
        'hit_rate': 'Hit rate',
        'units': 'Units',
        'roi': 'ROI',
        'valid': 'Valid pre-start locks',
        'proof_quality': 'Proof quality',
        'download_locked': 'Download locked proof CSV',
        'download_client': 'Download client-view CSV',
        'save_persistent': 'Re-save locked rows to this test ledger',
        'saved_persistent': 'Saved to persistent test ledger',
        'blocker_summary': 'Why rows were blocked',
        'blocked_preview': 'Blocked-row diagnostic preview',
        'no_research_candidates': 'No research/test candidates found.',
        'no_official_candidates': 'No official +EV candidates found. Research/test may still be usable.',
        'no_review_rows': 'No rows reached lock-candidate review.',
        'report_language': 'Report language',
        'public_only': 'Public/client-safe view',
        'report': 'Copy/paste report',
        'handoff': 'Handoff health',
        'saved_note': 'This version loads Pro Predictor handoff rows from session, local memory, and local JSON fallback.',
    },
    'es': {
        'title': 'Odds Lock Pro',
        'caption': 'Crea bloqueos investigación/prueba y ledgers persistentes.',
        'info': 'Usa esta página para bloquear filas antes de los juegos. El Dashboard Público lee el ledger guardado.',
        'test_window': 'ID de ventana de prueba',
        'test_window_help': 'Usa el mismo ID en el Dashboard Público, como test_01.',
        'input': 'Entrada',
        'use_session': 'Usar últimas filas guardadas/sesión',
        'upload': 'Subir CSV de predicciones o ledger bloqueado',
        'source': 'Fuente de entrada',
        'include_watch': 'Incluir filas watch/tracker',
        'analyst': 'Analista / marca',
        'max_units': 'Máximo de unidades por pick',
        'shortlist': 'Lista corta de máxima confianza',
        'use_shortlist': 'Usar lista corta',
        'max_shortlist': 'Máximo de filas',
        'min_shortlist_prob': 'Probabilidad mínima',
        'min_shortlist_score': 'Puntaje mínimo',
        'lock_research': 'Crear ledger investigación/prueba futuro',
        'lock': 'Crear ledger oficial +EV futuro',
        'research_lock_created': 'Filas investigación/prueba creadas y guardadas',
        'lock_created': 'Filas oficiales +EV creadas y guardadas',
        'research_lock_not_created': 'No se creó ledger investigación/prueba.',
        'lock_not_created': 'No se creó ledger oficial +EV.',
        'no_rows': 'No hay filas. Ejecuta Predictor Pro o sube un CSV.',
        'no_locked': 'Aún no hay filas bloqueadas.',
        'locked': 'Ledger bloqueado',
        'research_candidates_tab': 'Candidatos investigación/prueba',
        'official_candidates_tab': 'Candidatos oficiales +EV',
        'dashboard': 'Dashboard de prueba',
        'reports': 'Generador de reportes',
        'client': 'Vista cliente',
        'input_rows': 'Filas entrada',
        'persistent_rows': 'Ledger guardado',
        'reviewed': 'Revisadas',
        'research_candidates': 'Investigación/Prueba',
        'official_candidates': 'Oficial +EV',
        'rows': 'Filas',
        'resolved': 'Resueltas',
        'record': 'Récord',
        'hit_rate': 'Acierto',
        'units': 'Unidades',
        'roi': 'ROI',
        'valid': 'Bloqueos válidos antes del inicio',
        'proof_quality': 'Calidad prueba',
        'download_locked': 'Descargar CSV bloqueado',
        'download_client': 'Descargar CSV cliente',
        'save_persistent': 'Re-guardar filas bloqueadas',
        'saved_persistent': 'Guardado en ledger persistente',
        'blocker_summary': 'Por qué se bloquearon',
        'blocked_preview': 'Diagnóstico de filas bloqueadas',
        'no_research_candidates': 'No hay candidatos investigación/prueba.',
        'no_official_candidates': 'No hay candidatos +EV. Investigación/prueba aún puede servir.',
        'no_review_rows': 'Ninguna fila llegó a revisión.',
        'report_language': 'Idioma del reporte',
        'public_only': 'Vista segura público/cliente',
        'report': 'Reporte para copiar/pegar',
        'handoff': 'Salud del traspaso',
        'saved_note': 'Esta versión carga filas de Predictor Pro desde sesión, memoria local y JSON local.',
    },
}

RESEARCH_TEST_IGNORED_BLOCKERS = {
    'missing_decimal_price', 'missing_bookmaker_or_odds_source', 'invalid_decimal_price',
    'negative_model_edge', 'negative_expected_value', 'robust_ev_below_0', 'robust_profit80_below_0',
    'strict_robust_ev_below_1_5pct', 'price_range_risk_too_high', 'price_range_risk_above_profit_mode_limit',
}
HANDOFF_KEYS = [
    'pro_predictor_latest_rows',
    'pro_predictor_high_confidence_rows',
    'ara_latest_predictions',
    'what_are_the_odds_latest_rows',
    'odds_lock_pro_locked_rows',
    'public_proof_dashboard_refresh_rows',
]


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def csv_link(label: str, frame: pd.DataFrame, filename: str) -> None:
    data = base64.b64encode(frame.to_csv(index=False).encode('utf-8')).decode('ascii')
    st.markdown(
        f'<a href="data:text/csv;base64,{data}" download="{html.escape(filename)}" '
        f'style="display:block;text-align:center;background:#ef5350;color:white;'
        f'padding:.75rem 1rem;border-radius:.45rem;text-decoration:none;font-weight:700;">'
        f'{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def rows_from_sources(workspace_id: str) -> tuple[str, list[dict[str, Any]]]:
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return key, [dict(row) for row in rows if isinstance(row, dict)]
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    if rows:
        st.session_state[key] = rows
        return f'local:{key}', rows
    return '', []


def read_inputs(workspace_id: str) -> tuple[str, pd.DataFrame]:
    label, rows = rows_from_sources(workspace_id)
    use_session = st.checkbox(t('use_session'), value=bool(rows))
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    if use_session and rows:
        frames.append(pd.DataFrame(rows))
        names.append(label or 'saved_rows')
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


def numeric_best(frame: pd.DataFrame, names: list[str]) -> pd.Series:
    for name in names:
        if name in frame.columns:
            values = pd.to_numeric(frame[name], errors='coerce')
            if values.notna().any():
                if 'prob' in name.lower():
                    values = values.where(values <= 1.0, values / 100.0)
                return values
    return pd.Series(index=frame.index, dtype=float)


def shortlist_frame(frame: pd.DataFrame, *, use_shortlist: bool, max_rows: int, min_probability: float, min_score: float) -> pd.DataFrame:
    if frame.empty or not use_shortlist:
        return frame
    out = frame.copy()
    probability = numeric_best(out, ['model_probability', 'model_probability_clean', 'final_probability', 'probability', 'confidence_probability'])
    score = numeric_best(out, ['agent_score', 'scanner_strength_score', 'confidence_score', 'score'])
    if probability.notna().any():
        out['_shortlist_probability'] = probability
        out = out[out['_shortlist_probability'].fillna(0.0) >= float(min_probability)]
    if not out.empty and score.notna().any():
        out['_shortlist_score'] = score.reindex(out.index)
        out = out[out['_shortlist_score'].fillna(0.0) >= float(min_score)]
    sort_cols = [col for col in ['_shortlist_score', '_shortlist_probability', 'agent_score', 'scanner_strength_score', 'model_edge'] if col in out.columns]
    if sort_cols and not out.empty:
        out = out.sort_values(sort_cols, ascending=False, na_position='last')
    if int(max_rows) > 0:
        out = out.head(int(max_rows))
    return out.drop(columns=[col for col in ['_shortlist_probability', '_shortlist_score'] if col in out.columns], errors='ignore')


def split_blockers(value: Any) -> list[str]:
    text = safe_text(value)
    return [] if not text else [item.strip() for item in text.split(';') if item.strip()]


def research_remaining_blockers(row: Mapping[str, Any]) -> list[str]:
    return [item for item in split_blockers(row.get('lock_blockers')) if item not in RESEARCH_TEST_IGNORED_BLOCKERS]


def research_ignored_blockers(row: Mapping[str, Any]) -> list[str]:
    return [item for item in split_blockers(row.get('lock_blockers')) if item in RESEARCH_TEST_IGNORED_BLOCKERS]


def apply_research_mode(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    remaining, ignored, ready = [], [], []
    for row in out.to_dict(orient='records'):
        remaining_blockers = research_remaining_blockers(row)
        remaining.append('; '.join(remaining_blockers))
        ignored.append('; '.join(research_ignored_blockers(row)))
        ready.append(not remaining_blockers)
    out['research_lock_blockers'] = remaining
    out['ignored_value_blockers'] = ignored
    out['research_lock_ready'] = ready
    return out


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _first_float(row: Mapping[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = _safe_float(row.get(name))
        if value is not None:
            return value
    return None


def research_stake_units(row: Mapping[str, Any], *, max_units: float) -> float:
    incoming = _first_float(row, ['stake_units', 'recommended_stake_units'])
    if incoming is None or incoming <= 0:
        incoming = 1.0
    return round(max(0.0, min(float(max_units), incoming)), 2)


def research_lock_rows(frame: pd.DataFrame, *, analyst: str, max_units: float, workspace_id: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    locked_time = now_utc()
    locked_dt = parse_datetime_utc(locked_time)
    rows = []
    for row in frame.to_dict(orient='records'):
        if research_remaining_blockers(row):
            continue
        item = dict(row)
        original_blockers = split_blockers(item.get('lock_blockers'))
        item['locked_at_utc'] = locked_time
        item['analyst'] = analyst or 'private_analyst'
        item['test_window_id'] = workspace_id
        item['ledger_type'] = 'research_test_future_only'
        item['official_ev_pick'] = False
        item['official_lock_blockers'] = '; '.join(original_blockers)
        item['ignored_value_blockers'] = '; '.join(research_ignored_blockers(item))
        item['lock_blockers'] = ''
        item['official_lock_ready'] = False
        item['research_lock_ready'] = True
        item['stake_units'] = research_stake_units(item, max_units=max_units)
        item['proof_status'] = lock_status(item, locked_at=locked_dt)
        item['public_confidence'] = 'Research/Test'
        item['public_reason'] = 'Accuracy test lock; value blockers ignored. Not an official +EV pick.'
        item['profit_units'] = profit_units(item)
        item['proof_hash'] = proof_hash(item)
        item['proof_id'] = proof_id_from_hash(item['proof_hash'])
        rows.append(item)
    return pd.DataFrame(rows)


def mark_official_locked(frame: pd.DataFrame, workspace_id: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    out['test_window_id'] = workspace_id
    out['ledger_type'] = 'official_plus_ev_future_only'
    out['official_ev_pick'] = True
    return out


def publish_locked_rows(locked: pd.DataFrame, *, source_label: str, workspace_id: str) -> pd.DataFrame:
    if locked.empty:
        return pd.DataFrame()
    locked = locked.copy()
    locked['test_window_id'] = workspace_id
    existing = load_persistent_ledger(workspace_id=workspace_id)
    session_locked = pd.DataFrame(st.session_state.get('odds_lock_pro_locked_rows', []))
    combined = merge_ledgers(existing, locked, session_locked)
    saved = save_persistent_ledger(combined, workspace_id=workspace_id)
    final = saved if not saved.empty else filter_locked_proof_rows(locked)
    records = final.to_dict('records')
    for key in ['odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows', 'ara_latest_predictions']:
        st.session_state[key] = records
        save_held_rows(key, records, workspace_id)
    st.session_state['ara_latest_predictions_source'] = f'Odds Lock Pro {source_label}:{workspace_id}'
    return final


def blocker_summary(frame: pd.DataFrame, column: str = 'lock_blockers') -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame()
    counts: dict[str, int] = {}
    for value in frame[column].fillna('').astype(str):
        for item in value.split(';'):
            key = item.strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return pd.DataFrame([{'blocker': key, 'rows': value} for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))])


def show_blocked_diagnostics(frame: pd.DataFrame, *, blocker_column: str) -> None:
    if frame.empty:
        st.info(t('no_review_rows'))
        return
    blocked = blocker_summary(frame, column=blocker_column)
    if not blocked.empty:
        st.subheader(t('blocker_summary'))
        st.dataframe(blocked, use_container_width=True, hide_index=True)
    cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price', 'bookmaker', 'odds_source', 'event_start_utc', 'agent_decision', 'lock_ready', 'prelock_status', 'lock_blockers', 'research_lock_blockers', 'ignored_value_blockers'] if col in frame.columns]
    st.subheader(t('blocked_preview'))
    st.dataframe(frame[cols] if cols else frame, use_container_width=True, hide_index=True)


def show_candidates(frame: pd.DataFrame) -> None:
    cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price', 'bookmaker', 'odds_source', 'agent_decision', 'agent_score', 'scanner_strength_score', 'model_edge', 'stake_units', 'prelock_status', 'official_lock_ready', 'research_lock_ready', 'research_lock_blockers', 'ignored_value_blockers', 'public_confidence', 'public_reason'] if col in frame.columns]
    st.dataframe(frame[cols] if cols else frame, use_container_width=True, hide_index=True)


def exposure_summary(frame: pd.DataFrame, *, daily_limit_units: float, sport_limit_units: float) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=['scope', 'stake_units', 'limit_units', 'status'])
    stake = pd.to_numeric(frame.get('stake_units', pd.Series(dtype=float)), errors='coerce').fillna(0.0)
    rows = [{'scope': 'daily_total', 'stake_units': round(float(stake.sum()), 4), 'limit_units': float(daily_limit_units), 'status': 'ok' if float(stake.sum()) <= float(daily_limit_units) else 'over_limit'}]
    if 'sport' in frame.columns:
        tmp = frame.copy()
        tmp['_stake_units_numeric'] = stake
        for sport, group in tmp.groupby('sport', dropna=False):
            total = float(group['_stake_units_numeric'].sum())
            rows.append({'scope': f'sport:{safe_text(sport) or "unknown"}', 'stake_units': round(total, 4), 'limit_units': float(sport_limit_units), 'status': 'ok' if total <= float(sport_limit_units) else 'over_limit'})
    return pd.DataFrame(rows)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))
st.caption(t('saved_note'))

with st.expander(t('input'), expanded=True):
    workspace_input = st.text_input(t('test_window'), value=st.session_state.get('aba_test_window_id', 'test_01'), help=t('test_window_help'))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state['aba_test_window_id'] = workspace_id
    source_name, raw = read_inputs(workspace_id)
    include_watch = st.checkbox(t('include_watch'), value=True)
    analyst = st.text_input(t('analyst'), value='ABA Signal Pro · Powered by Reparodynamics')
    max_units = st.number_input(t('max_units'), min_value=0.25, max_value=10.0, value=1.0, step=0.25)
    daily_limit = st.number_input('Daily exposure limit', min_value=0.25, max_value=500.0, value=500.0, step=5.0)
    sport_limit = st.number_input('Per-sport exposure limit', min_value=0.25, max_value=500.0, value=500.0, step=5.0)

persistent_locked = load_persistent_ledger(workspace_id=workspace_id)
normalized_for_upload = normalize_frame(raw) if not raw.empty else pd.DataFrame()
uploaded_locked = filter_locked_proof_rows(normalized_for_upload) if not normalized_for_upload.empty and has_proof_fields(normalized_for_upload) else pd.DataFrame()

if raw.empty and persistent_locked.empty:
    st.caption(f"{t('source')}: none")
    st.caption(f"Active test ledger: {workspace_id}")
    st.warning(t('no_rows'))
    st.stop()

st.caption(f"{t('source')}: {source_name or 'persistent ledger'}")
st.caption(f"Active test ledger: {workspace_id}")

normalized = normalized_for_upload
if not normalized.empty:
    with st.expander(t('shortlist'), expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        use_shortlist = c1.checkbox(t('use_shortlist'), value=False)
        max_shortlist = c2.number_input(t('max_shortlist'), min_value=1, max_value=500, value=500, step=5)
        min_shortlist_prob = c3.number_input(t('min_shortlist_prob'), min_value=0.0, max_value=0.99, value=0.00, step=0.01)
        min_shortlist_score = c4.number_input(t('min_shortlist_score'), min_value=0.0, max_value=100.0, value=0.0, step=1.0)
    working = shortlist_frame(normalized, use_shortlist=bool(use_shortlist), max_rows=int(max_shortlist), min_probability=float(min_shortlist_prob), min_score=float(min_shortlist_score))
    review_rows = prepare_lock_candidates(working, include_watch=include_watch, strict=False, require_future=True)
    review_rows = apply_research_mode(review_rows)
else:
    working = pd.DataFrame()
    review_rows = pd.DataFrame()

official_candidates = review_rows[review_rows.get('official_lock_ready', pd.Series(dtype=bool)).fillna(False)].copy() if not review_rows.empty else pd.DataFrame()
research_candidates = review_rows[review_rows.get('research_lock_ready', pd.Series(dtype=bool)).fillna(False)].copy() if not review_rows.empty else pd.DataFrame()
session_locked = filter_locked_proof_rows(pd.DataFrame(st.session_state.get('odds_lock_pro_locked_rows', [])))
active_locked = merge_ledgers(persistent_locked, session_locked, uploaded_locked)

status_cols = st.columns(6)
status_cols[0].metric(t('input_rows'), int(len(normalized)))
status_cols[1].metric(t('persistent_rows'), int(len(persistent_locked)))
status_cols[2].metric(t('reviewed'), int(len(review_rows)))
status_cols[3].metric(t('research_candidates'), int(len(research_candidates)))
status_cols[4].metric(t('official_candidates'), int(len(official_candidates)))
status_cols[5].metric('Uploaded locked', int(len(uploaded_locked)))

button_cols = st.columns(2)
research_clicked = button_cols[0].button(t('lock_research'), type='primary', use_container_width=True, disabled=research_candidates.empty)
official_clicked = button_cols[1].button(t('lock'), type='secondary', use_container_width=True, disabled=official_candidates.empty)

if research_clicked:
    locked = research_lock_rows(research_candidates, analyst=analyst, max_units=float(max_units), workspace_id=workspace_id)
    if locked.empty:
        st.error(t('research_lock_not_created'))
        show_blocked_diagnostics(review_rows, blocker_column='research_lock_blockers')
    else:
        active_locked = publish_locked_rows(locked, source_label='research/test', workspace_id=workspace_id)
        st.success(f"{t('research_lock_created')}: {len(locked)} / saved {len(active_locked)}")

if official_clicked:
    locked = lock_rows(working, analyst=analyst, max_units=float(max_units), include_watch=include_watch, strict=True, require_future=True)
    locked = mark_official_locked(locked, workspace_id)
    if locked.empty:
        st.error(t('lock_not_created'))
        show_blocked_diagnostics(review_rows, blocker_column='lock_blockers')
    else:
        active_locked = publish_locked_rows(locked, source_label='official +EV', workspace_id=workspace_id)
        st.success(f"{t('lock_created')}: {len(locked)} / saved {len(active_locked)}")

summary = summarize_locked_picks(active_locked)
audit = proof_audit_summary(active_locked)
health_frame_source = active_locked if not active_locked.empty else (research_candidates if not research_candidates.empty else official_candidates)

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

tabs = st.tabs([t('research_candidates_tab'), t('official_candidates_tab'), t('locked'), t('dashboard'), t('reports'), 'Exposure', t('client')])

with tabs[0]:
    if research_candidates.empty:
        st.warning(t('no_research_candidates'))
        show_blocked_diagnostics(review_rows, blocker_column='research_lock_blockers')
    else:
        show_candidates(research_candidates)

with tabs[1]:
    if official_candidates.empty:
        st.warning(t('no_official_candidates'))
        show_blocked_diagnostics(review_rows, blocker_column='lock_blockers')
    else:
        show_candidates(official_candidates)

with tabs[2]:
    if active_locked.empty:
        st.warning(t('no_locked'))
    else:
        st.dataframe(active_locked, use_container_width=True, hide_index=True)
        csv_link(t('download_locked'), active_locked, f'odds_lock_pro_locked_ledger_{workspace_id}.csv')
        if st.button(t('save_persistent'), use_container_width=True):
            saved = publish_locked_rows(active_locked, source_label='manual-save', workspace_id=workspace_id)
            st.success(f"{t('saved_persistent')}: {workspace_id} / {len(saved)} rows")

with tabs[3]:
    st.json({**summary, **audit})
    by_sport = performance_by_group(active_locked, 'sport')
    if not by_sport.empty:
        st.subheader('By sport' if LANG == 'en' else 'Por deporte')
        st.dataframe(by_sport, use_container_width=True, hide_index=True)
    by_market = performance_by_group(active_locked, 'market_type')
    if not by_market.empty:
        st.subheader('By market' if LANG == 'en' else 'Por mercado')
        st.dataframe(by_market, use_container_width=True, hide_index=True)

with tabs[4]:
    report_language = st.radio(t('report_language'), ['English', 'Español'], horizontal=True, index=0 if LANG == 'en' else 1)
    public_only = st.checkbox(t('public_only'), value=True, key='report_public_only')
    report_text = daily_report(active_locked, language=report_language, public_only=public_only)
    st.text_area(t('report'), value=report_text, height=360)

with tabs[5]:
    exposure = exposure_summary(active_locked, daily_limit_units=float(daily_limit), sport_limit_units=float(sport_limit))
    st.dataframe(exposure, use_container_width=True, hide_index=True)

with tabs[6]:
    public_only_client = st.checkbox(t('public_only'), value=True, key='client_public_only')
    client = client_view(active_locked, public_only=public_only_client)
    st.dataframe(client, use_container_width=True, hide_index=True)
    csv_link(t('download_client'), client, f'odds_lock_pro_client_view_{workspace_id}.csv')

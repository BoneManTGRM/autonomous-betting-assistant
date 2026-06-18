from __future__ import annotations

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
from autonomous_betting_agent.row_normalizer import normalize_frame, safe_text

st.set_page_config(page_title='Odds Lock Pro', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='odds_lock_pro_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Odds Lock Pro',
        'caption': 'Timestamped proof ledger, performance dashboard, reports, bankroll controls, and client-ready views.',
        'info': 'This page now gives both outputs at the same time: Research/Test locks for accuracy testing and Official +EV locks for betting-value proof.',
        'test_window': 'Test Window ID',
        'test_window_help': 'Use a simple ID such as test_01, test_02, etc. Each ID saves to its own persistent proof ledger.',
        'active_test_window': 'Active test ledger',
        'use_session': 'Use latest rows from session',
        'upload': 'Upload prediction, high-confidence tracker, or locked-ledger CSV',
        'source': 'Input source',
        'research_help': 'Research/Test locks future predictions for accuracy testing and ignores EV/profitability blockers. It does not label them as official +EV betting picks.',
        'official_help': 'Official +EV locks only rows that pass the strict betting-value gates.',
        'analyst': 'Analyst / brand name',
        'max_units': 'Max stake units per pick',
        'daily_limit': 'Daily exposure limit',
        'sport_limit': 'Per-sport exposure limit',
        'include_watch': 'Include watch-only / tracker rows',
        'shortlist': 'Highest-confidence shortlist',
        'use_shortlist': 'Use highest-confidence shortlist before locking',
        'max_shortlist': 'Max shortlist rows',
        'min_shortlist_prob': 'Minimum model probability',
        'min_shortlist_score': 'Minimum agent score',
        'shortlisted': 'Shortlisted',
        'lock': 'Create official +EV future-only ledger',
        'lock_research': 'Create research/test future-only ledger',
        'save_persistent': 'Save locked rows to this test ledger',
        'saved_persistent': 'Saved to persistent test ledger',
        'official_candidates_tab': 'Official +EV candidates',
        'research_candidates_tab': 'Research/Test candidates',
        'locked': 'Locked proof ledger',
        'dashboard': 'Proof dashboard',
        'reports': 'Report generator',
        'bankroll': 'Bankroll / exposure',
        'client': 'Client view',
        'rows': 'Rows',
        'input_rows': 'Input rows',
        'reviewed': 'Reviewed',
        'official_candidates': 'Official +EV',
        'research_candidates': 'Research/Test',
        'uploaded_locked': 'Uploaded locked',
        'resolved': 'Resolved',
        'record': 'Record',
        'hit_rate': 'Hit rate',
        'units': 'Units',
        'roi': 'ROI',
        'valid': 'Valid pre-start locks',
        'proof_quality': 'Proof quality',
        'download_locked': 'Download locked proof CSV',
        'download_client': 'Download client-view CSV',
        'download_private': 'Download private audit CSV',
        'no_rows': 'No rows found. Run What Are the Odds first or upload a CSV.',
        'no_locked': 'No locked proof rows yet. Create a locked proof ledger or upload a ledger with proof_id and locked_at_utc.',
        'no_official_candidates': 'No official +EV candidates found. These rows can still be valid research/test picks, but they did not pass strict betting-value gates.',
        'no_research_candidates': 'No research/test candidates found. Rows must still be future predictions with core event and pick fields.',
        'no_review_rows': 'No rows reached lock-candidate review. Turn on watch/tracker rows for legacy tracker files, or send rows from Pro Predictor/What Are the Odds.',
        'lock_created': 'Created official +EV locked proof rows',
        'research_lock_created': 'Created research/test locked rows',
        'lock_not_created': 'No official +EV ledger was created.',
        'research_lock_not_created': 'No research/test ledger was created.',
        'lock_not_created_detail': 'The button worked, but every reviewed row was blocked for this ledger type. The diagnostics below show exactly what is missing.',
        'lock_not_created_no_review': 'The button worked, but no rows qualified for lock review. The upload may be a results-only file or may lack event/prediction fields.',
        'blocker_summary': 'Why rows were blocked',
        'blocked_preview': 'Blocked-row diagnostic preview',
        'public_only': 'Public/client-safe view',
        'report_language': 'Report language',
        'report': 'Copy/paste report',
        'handoff': 'Four-tool handoff health',
    },
    'es': {
        'title': 'Odds Lock Pro',
        'caption': 'Ledger con prueba por timestamp, dashboard de rendimiento, reportes, control de unidades y vista para clientes.',
        'info': 'Esta página ahora da ambos resultados al mismo tiempo: Investigación/Prueba para medir acierto y Oficial +EV para prueba de valor de apuesta.',
        'test_window': 'ID de ventana de prueba',
        'test_window_help': 'Usa un ID simple como test_01, test_02, etc. Cada ID guarda su propio ledger persistente.',
        'active_test_window': 'Ledger de prueba activo',
        'use_session': 'Usar últimas filas de la sesión',
        'upload': 'Subir CSV de predicciones, tracker de alta confianza o ledger bloqueado',
        'source': 'Fuente de entrada',
        'research_help': 'Investigación/Prueba bloquea predicciones futuras para medir acierto e ignora bloqueos de EV/rentabilidad. No las etiqueta como picks oficiales +EV.',
        'official_help': 'Oficial +EV bloquea solamente filas que pasan filtros estrictos de valor de apuesta.',
        'analyst': 'Analista / marca',
        'max_units': 'Máximo de unidades por pick',
        'daily_limit': 'Límite diario de exposición',
        'sport_limit': 'Límite de exposición por deporte',
        'include_watch': 'Incluir filas watch/tracker',
        'shortlist': 'Lista corta de máxima confianza',
        'use_shortlist': 'Usar lista corta antes de bloquear',
        'max_shortlist': 'Máximo de filas en lista corta',
        'min_shortlist_prob': 'Probabilidad mínima del modelo',
        'min_shortlist_score': 'Puntaje mínimo del agente',
        'shortlisted': 'Lista corta',
        'lock': 'Crear ledger oficial +EV solo de eventos futuros',
        'lock_research': 'Crear ledger investigación/prueba solo de eventos futuros',
        'save_persistent': 'Guardar filas bloqueadas en este ledger de prueba',
        'saved_persistent': 'Guardado en ledger persistente de prueba',
        'official_candidates_tab': 'Candidatos oficiales +EV',
        'research_candidates_tab': 'Candidatos investigación/prueba',
        'locked': 'Ledger bloqueado',
        'dashboard': 'Dashboard de prueba',
        'reports': 'Generador de reportes',
        'bankroll': 'Bankroll / exposición',
        'client': 'Vista para clientes',
        'rows': 'Filas',
        'input_rows': 'Filas cargadas',
        'reviewed': 'Revisadas',
        'official_candidates': 'Oficial +EV',
        'research_candidates': 'Investigación/Prueba',
        'uploaded_locked': 'Ledger subido',
        'resolved': 'Resueltos',
        'record': 'Récord',
        'hit_rate': 'Tasa de acierto',
        'units': 'Unidades',
        'roi': 'ROI',
        'valid': 'Bloqueos válidos antes del inicio',
        'proof_quality': 'Calidad prueba',
        'download_locked': 'Descargar CSV de prueba bloqueada',
        'download_client': 'Descargar CSV para clientes',
        'download_private': 'Descargar CSV privado de auditoría',
        'no_rows': 'No se encontraron filas. Ejecuta What Are the Odds primero o sube un CSV.',
        'no_locked': 'Aún no hay filas bloqueadas con prueba. Crea bloqueos o sube un ledger con proof_id y locked_at_utc.',
        'no_official_candidates': 'No hay candidatos oficiales +EV. Estas filas pueden servir como prueba de acierto, pero no pasaron los filtros estrictos de valor de apuesta.',
        'no_research_candidates': 'No hay candidatos de investigación/prueba. Las filas deben ser predicciones futuras con campos básicos de evento y pick.',
        'no_review_rows': 'Ninguna fila llegó a revisión. Activa filas watch/tracker para archivos legacy, o envía filas desde Predictor Pro/What Are the Odds.',
        'lock_created': 'Filas oficiales +EV bloqueadas creadas',
        'research_lock_created': 'Filas investigación/prueba bloqueadas creadas',
        'lock_not_created': 'No se creó ningún ledger oficial +EV.',
        'research_lock_not_created': 'No se creó ningún ledger de investigación/prueba.',
        'lock_not_created_detail': 'El botón funcionó, pero todas las filas revisadas fueron bloqueadas para este tipo de ledger. El diagnóstico abajo muestra exactamente qué falta.',
        'lock_not_created_no_review': 'El botón funcionó, pero ninguna fila calificó para revisión. Probablemente es un archivo solo de resultados o sin evento/pronóstico.',
        'blocker_summary': 'Por qué se bloquearon las filas',
        'blocked_preview': 'Vista diagnóstica de filas bloqueadas',
        'public_only': 'Vista segura para público/clientes',
        'report_language': 'Idioma del reporte',
        'report': 'Reporte para copiar/pegar',
        'handoff': 'Salud del traspaso entre herramientas',
    },
}

RESEARCH_TEST_IGNORED_BLOCKERS = {
    'missing_decimal_price',
    'missing_bookmaker_or_odds_source',
    'invalid_decimal_price',
    'negative_model_edge',
    'negative_expected_value',
    'robust_ev_below_0',
    'robust_profit80_below_0',
    'strict_robust_ev_below_1_5pct',
    'price_range_risk_too_high',
    'price_range_risk_above_profit_mode_limit',
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def session_rows() -> tuple[str, list[dict]]:
    sources = [
        ('what_are_the_odds_latest_rows', 'What Are the Odds'),
        ('pro_predictor_latest_rows', 'Pro Predictor'),
        ('pro_predictor_high_confidence_rows', 'Pro Predictor high-confidence'),
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
    sortable = False
    if probability.notna().any():
        out['_shortlist_probability'] = probability
        out = out[out['_shortlist_probability'].fillna(0.0) >= float(min_probability)]
        sortable = True
    if not out.empty and score.notna().any():
        score = score.reindex(out.index)
        out['_shortlist_score'] = score
        out = out[out['_shortlist_score'].fillna(0.0) >= float(min_score)]
        sortable = True
    if out.empty:
        return out.drop(columns=[col for col in ['_shortlist_probability', '_shortlist_score'] if col in out.columns], errors='ignore')
    sort_cols = [col for col in ['_shortlist_score', '_shortlist_probability', 'agent_score', 'scanner_strength_score', 'model_edge'] if col in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, ascending=False, na_position='last')
    if sortable and int(max_rows) > 0:
        out = out.head(int(max_rows))
    return out.drop(columns=[col for col in ['_shortlist_probability', '_shortlist_score'] if col in out.columns], errors='ignore')


def exposure_summary(frame: pd.DataFrame, *, daily_limit_units: float, sport_limit_units: float) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=['scope', 'stake_units', 'limit_units', 'status'])
    stake = pd.to_numeric(frame.get('stake_units', pd.Series(dtype=float)), errors='coerce').fillna(0.0)
    rows = [{
        'scope': 'daily_total',
        'stake_units': round(float(stake.sum()), 4),
        'limit_units': float(daily_limit_units),
        'status': 'ok' if float(stake.sum()) <= float(daily_limit_units) else 'over_limit',
    }]
    if 'sport' in frame.columns:
        tmp = frame.copy()
        tmp['_stake_units_numeric'] = stake
        for sport, group in tmp.groupby('sport', dropna=False):
            total = float(group['_stake_units_numeric'].sum())
            rows.append({
                'scope': f'sport:{safe_text(sport) or "unknown"}',
                'stake_units': round(total, 4),
                'limit_units': float(sport_limit_units),
                'status': 'ok' if total <= float(sport_limit_units) else 'over_limit',
            })
    return pd.DataFrame(rows)


def split_blockers(value: Any) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [item.strip() for item in text.split(';') if item.strip()]


def research_remaining_blockers(row: Mapping[str, Any]) -> list[str]:
    return [item for item in split_blockers(row.get('lock_blockers')) if item not in RESEARCH_TEST_IGNORED_BLOCKERS]


def research_ignored_blockers(row: Mapping[str, Any]) -> list[str]:
    return [item for item in split_blockers(row.get('lock_blockers')) if item in RESEARCH_TEST_IGNORED_BLOCKERS]


def apply_research_mode(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    remaining: list[str] = []
    ignored: list[str] = []
    ready: list[bool] = []
    for row in out.to_dict(orient='records'):
        remaining_blockers = research_remaining_blockers(row)
        ignored_blockers = research_ignored_blockers(row)
        remaining.append('; '.join(remaining_blockers))
        ignored.append('; '.join(ignored_blockers))
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
        item['public_reason'] = 'Accuracy test lock; EV/profitability blockers ignored. Not an official +EV betting pick.'
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


def blocker_summary(frame: pd.DataFrame, column: str = 'lock_blockers') -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame()
    counts: dict[str, int] = {}
    for value in frame[column].fillna('').astype(str):
        for item in value.split(';'):
            key = item.strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    if not counts:
        return pd.DataFrame()
    return pd.DataFrame(
        [{'blocker': key, 'rows': value} for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    )


def diagnostic_columns(frame: pd.DataFrame) -> list[str]:
    preferred = [
        'event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price',
        'bookmaker', 'odds_source', 'event_start_utc', 'agent_decision', 'decision', 'lock_ready',
        'prelock_status', 'lock_blockers', 'research_lock_blockers', 'ignored_value_blockers',
        'result_status', 'source_file',
    ]
    return [col for col in preferred if col in frame.columns]


def show_blocked_diagnostics(frame: pd.DataFrame, *, blocker_column: str) -> None:
    if frame.empty:
        st.info(t('no_review_rows'))
        return
    blocked = blocker_summary(frame, column=blocker_column)
    if not blocked.empty:
        st.subheader(t('blocker_summary'))
        st.dataframe(blocked, use_container_width=True, hide_index=True)
    cols = diagnostic_columns(frame)
    st.subheader(t('blocked_preview'))
    st.dataframe(frame[cols] if cols else frame, use_container_width=True, hide_index=True)


def show_candidates(frame: pd.DataFrame) -> None:
    show_cols = [col for col in [
        'event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price',
        'bookmaker', 'odds_source', 'agent_decision', 'agent_score', 'scanner_strength_score',
        'model_edge', 'stake_units', 'prelock_status', 'official_lock_ready', 'research_lock_ready',
        'research_lock_blockers', 'ignored_value_blockers', 'public_confidence', 'public_reason',
    ] if col in frame.columns]
    st.dataframe(frame[show_cols] if show_cols else frame, use_container_width=True, hide_index=True)


def publish_locked_rows(locked: pd.DataFrame, *, source_label: str, workspace_id: str) -> pd.DataFrame:
    if locked.empty:
        return pd.DataFrame()
    locked = locked.copy()
    locked['test_window_id'] = workspace_id
    st.session_state['odds_lock_pro_locked_rows'] = locked.to_dict('records')
    st.session_state['ara_latest_predictions'] = locked.to_dict('records')
    st.session_state['ara_latest_predictions_source'] = f'Odds Lock Pro {source_label}:{workspace_id}'
    return filter_locked_proof_rows(locked)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))

workspace_input = st.sidebar.text_input(
    t('test_window'),
    value=st.session_state.get('aba_test_window_id', 'test_01'),
    help=t('test_window_help'),
)
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id
st.sidebar.caption(f"{t('active_test_window')}: {workspace_id}")

source_name, raw = read_inputs()
st.caption(f"{t('source')}: {source_name or 'none'}")
st.caption(f"{t('active_test_window')}: {workspace_id}")
if raw.empty:
    st.warning(t('no_rows'))
    st.stop()

normalized = normalize_frame(raw)
st.caption(t('research_help'))
st.caption(t('official_help'))
include_watch = st.checkbox(t('include_watch'), value=True)
analyst = st.text_input(t('analyst'), value='ReparoEdge · Powered by Reparodynamics')
max_units = st.number_input(t('max_units'), min_value=0.25, max_value=10.0, value=1.0, step=0.25)
daily_limit = st.number_input(t('daily_limit'), min_value=0.25, max_value=500.0, value=500.0, step=5.0)
sport_limit = st.number_input(t('sport_limit'), min_value=0.25, max_value=500.0, value=500.0, step=5.0)

with st.expander(t('shortlist'), expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    use_shortlist = c1.checkbox(t('use_shortlist'), value=False)
    max_shortlist = c2.number_input(t('max_shortlist'), min_value=1, max_value=500, value=500, step=5)
    min_shortlist_prob = c3.number_input(t('min_shortlist_prob'), min_value=0.0, max_value=0.99, value=0.00, step=0.01)
    min_shortlist_score = c4.number_input(t('min_shortlist_score'), min_value=0.0, max_value=100.0, value=0.0, step=1.0)

working = shortlist_frame(
    normalized,
    use_shortlist=bool(use_shortlist),
    max_rows=int(max_shortlist),
    min_probability=float(min_shortlist_prob),
    min_score=float(min_shortlist_score),
)
review_rows = prepare_lock_candidates(working, include_watch=include_watch, strict=False, require_future=True)
review_rows = apply_research_mode(review_rows)
official_candidates = review_rows[review_rows.get('official_lock_ready', pd.Series(dtype=bool)).fillna(False)].copy() if not review_rows.empty else pd.DataFrame()
research_candidates = review_rows[review_rows.get('research_lock_ready', pd.Series(dtype=bool)).fillna(False)].copy() if not review_rows.empty else pd.DataFrame()
existing_locked = filter_locked_proof_rows(pd.DataFrame(st.session_state.get('odds_lock_pro_locked_rows', [])))
uploaded_locked = filter_locked_proof_rows(normalized) if has_proof_fields(normalized) else pd.DataFrame()

status_cols = st.columns(6)
status_cols[0].metric(t('input_rows'), int(len(normalized)))
status_cols[1].metric(t('shortlisted'), int(len(working)))
status_cols[2].metric(t('reviewed'), int(len(review_rows)))
status_cols[3].metric(t('research_candidates'), int(len(research_candidates)))
status_cols[4].metric(t('official_candidates'), int(len(official_candidates)))
status_cols[5].metric(t('uploaded_locked'), int(len(uploaded_locked)))

button_cols = st.columns(2)
research_clicked = button_cols[0].button(t('lock_research'), type='primary', use_container_width=True)
official_clicked = button_cols[1].button(t('lock'), type='secondary', use_container_width=True)

if research_clicked:
    locked = research_lock_rows(research_candidates, analyst=analyst, max_units=float(max_units), workspace_id=workspace_id)
    if locked.empty:
        st.error(t('research_lock_not_created'))
        st.warning(t('lock_not_created_no_review') if review_rows.empty else t('lock_not_created_detail'))
        show_blocked_diagnostics(review_rows, blocker_column='research_lock_blockers')
    else:
        existing_locked = publish_locked_rows(locked, source_label='research/test', workspace_id=workspace_id)
        st.success(f"{t('research_lock_created')}: {len(locked)}")

if official_clicked:
    locked = lock_rows(working, analyst=analyst, max_units=float(max_units), include_watch=include_watch, strict=True, require_future=True)
    locked = mark_official_locked(locked, workspace_id)
    if locked.empty:
        st.error(t('lock_not_created'))
        st.warning(t('lock_not_created_no_review') if review_rows.empty else t('lock_not_created_detail'))
        show_blocked_diagnostics(review_rows, blocker_column='lock_blockers')
    else:
        existing_locked = publish_locked_rows(locked, source_label='official +EV', workspace_id=workspace_id)
        st.success(f"{t('lock_created')}: {len(locked)}")

active_locked = merge_ledgers(existing_locked, uploaded_locked)
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

tabs = st.tabs([t('research_candidates_tab'), t('official_candidates_tab'), t('locked'), t('dashboard'), t('reports'), t('bankroll'), t('client')])

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
        st.download_button(t('download_locked'), active_locked.to_csv(index=False), file_name=f'odds_lock_pro_locked_ledger_{workspace_id}.csv', mime='text/csv')
        if st.button(t('save_persistent'), use_container_width=True):
            combined = merge_ledgers(load_persistent_ledger(workspace_id=workspace_id), active_locked)
            saved = save_persistent_ledger(combined, workspace_id=workspace_id)
            st.session_state['odds_lock_pro_locked_rows'] = saved.to_dict('records')
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
    st.download_button(t('download_client') if public_only_client else t('download_private'), client.to_csv(index=False), file_name=f'odds_lock_pro_client_view_{workspace_id}.csv' if public_only_client else f'odds_lock_pro_private_audit_{workspace_id}.csv', mime='text/csv')

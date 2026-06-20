from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.all_high_confidence_locker import lock_all_high_confidence_rows
from autonomous_betting_agent.commercial_platform_tools import (
    filter_locked_proof_rows,
    merge_ledgers,
    normalize_workspace_id,
    proof_audit_summary,
)
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='All High Confidence Locker', layout='wide')
LANG = render_app_sidebar('all_high_confidence_locker', language_key='all_high_confidence_locker_language', selector='radio')

REPO_ROOT = Path(__file__).resolve().parents[1]
INTERNAL_LEDGER_PATH = REPO_ROOT / 'data' / 'all_high_confidence_internal_ledger.csv'
INTERNAL_SESSION_KEY = 'all_high_confidence_locked_rows'
RESEARCH_SESSION_KEY = 'research_proof_dashboard_rows'

TEXT = {
    'en': {
        'title': 'All High Confidence Locker',
        'caption': 'Accept every supported high-confidence row for large-sample internal proof testing.',
        'note': 'This mode is for volume testing only. Rows are marked internal/research and are isolated from the official +EV public proof stores. Tennis/ATP/WTA/ITF/Challenger rows are still rejected.',
        'workspace': 'Workspace ID',
        'use_session': 'Use latest saved/session rows',
        'upload': 'Upload Pro Predictor high-confidence CSV',
        'analyst': 'Analyst / brand name',
        'max_units': 'Max stake units per pick',
        'create': 'Create all reviewed high-confidence internal ledger',
        'created': 'Created and saved all high-confidence internal rows',
        'no_rows': 'No rows found. Upload a CSV or run Pro Predictor first.',
        'source': 'Source',
        'input_rows': 'Input rows',
        'locked_rows': 'Locked/internal rows',
        'rejected_rows': 'Rejected rows',
        'saved_rows': 'Saved internal ledger rows',
        'download': 'Download all-high-confidence internal CSV',
        'rejected': 'Rejected unsupported rows',
    },
    'es': {
        'title': 'Bloqueador Alta Confianza Total',
        'caption': 'Acepta todas las filas soportadas de alta confianza para prueba interna de gran muestra.',
        'note': 'Este modo es solo para prueba de volumen. Las filas se marcan internas/investigación y están aisladas de las pruebas oficiales +EV públicas. Tenis/ATP/WTA/ITF/Challenger se rechaza.',
        'workspace': 'ID de workspace',
        'use_session': 'Usar últimas filas guardadas/sesión',
        'upload': 'Subir CSV alta confianza de Predictor Pro',
        'analyst': 'Analista / marca',
        'max_units': 'Máximo de unidades por pick',
        'create': 'Crear ledger interno con todas las filas alta confianza',
        'created': 'Filas internas alta confianza creadas y guardadas',
        'no_rows': 'No hay filas. Sube un CSV o ejecuta Predictor Pro primero.',
        'source': 'Fuente',
        'input_rows': 'Filas de entrada',
        'locked_rows': 'Filas internas bloqueadas',
        'rejected_rows': 'Filas rechazadas',
        'saved_rows': 'Filas internas guardadas',
        'download': 'Descargar CSV interno alta confianza',
        'rejected': 'Filas rechazadas no soportadas',
    },
}

HANDOFF_KEYS = [
    'pro_predictor_latest_rows',
    'pro_predictor_high_confidence_rows',
    'ara_latest_predictions',
    'what_are_the_odds_latest_rows',
]


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def internal_ledger_path(workspace_id: str) -> Path:
    workspace = normalize_workspace_id(workspace_id)
    if workspace in {'default', 'shared', 'main'}:
        return INTERNAL_LEDGER_PATH
    return INTERNAL_LEDGER_PATH.with_name(f'{INTERNAL_LEDGER_PATH.stem}_{workspace}{INTERNAL_LEDGER_PATH.suffix}')


def load_internal_ledger(workspace_id: str) -> pd.DataFrame:
    session_rows = st.session_state.get(INTERNAL_SESSION_KEY) or []
    frames: list[pd.DataFrame] = []
    if session_rows:
        frames.append(pd.DataFrame(session_rows))
    path = internal_ledger_path(workspace_id)
    try:
        if path.exists():
            frames.append(pd.read_csv(path))
    except Exception:
        pass
    return merge_ledgers(*frames) if frames else pd.DataFrame()


def save_internal_ledger(frame: pd.DataFrame | list[dict[str, Any]], workspace_id: str) -> pd.DataFrame:
    cleaned = filter_locked_proof_rows(frame)
    if cleaned.empty:
        return pd.DataFrame()
    records = cleaned.to_dict('records')
    st.session_state[INTERNAL_SESSION_KEY] = records
    st.session_state[RESEARCH_SESSION_KEY] = records
    try:
        path = internal_ledger_path(workspace_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        cleaned.to_csv(path, index=False)
    except Exception:
        pass
    return cleaned


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
    source, rows = rows_from_sources(workspace_id)
    use_session = st.checkbox(t('use_session'), value=bool(rows))
    frames: list[pd.DataFrame] = []
    labels: list[str] = []
    if use_session and rows:
        frames.append(pd.DataFrame(rows))
        labels.append(source or 'session')
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                frames.append(frame)
                labels.append(upload.name)
            except Exception as exc:
                st.warning(f'{upload.name}: {exc}')
    if not frames:
        return '', pd.DataFrame()
    return ', '.join(labels), pd.concat(frames, ignore_index=True, sort=False)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))

workspace_input = st.text_input(t('workspace'), value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id
analyst = st.text_input(t('analyst'), value='ABA Signal Pro · Powered by Reparodynamics')
max_units = st.number_input(t('max_units'), min_value=0.25, max_value=10.0, value=1.0, step=0.25)

source_name, raw = read_inputs(workspace_id)
persistent = load_internal_ledger(workspace_id)

st.caption(f"{t('source')}: {source_name or 'none'}")
metrics = st.columns(4)
metrics[0].metric(t('input_rows'), int(len(raw)))
metrics[3].metric(t('saved_rows'), int(len(persistent)))

if raw.empty and persistent.empty:
    st.warning(t('no_rows'))
    st.stop()

if st.button(t('create'), type='primary', use_container_width=True, disabled=raw.empty):
    locked, rejected = lock_all_high_confidence_rows(raw, analyst=analyst, workspace_id=workspace_id, max_units=float(max_units))
    if locked.empty:
        st.error(t('no_rows'))
    else:
        existing = load_internal_ledger(workspace_id)
        combined = merge_ledgers(existing, locked)
        final = save_internal_ledger(combined, workspace_id)
        st.success(f"{t('created')}: {len(locked)} / saved {len(final)}")
        st.session_state['all_high_confidence_rejected_rows'] = rejected.to_dict('records')

active = load_internal_ledger(workspace_id)
rejected = pd.DataFrame(st.session_state.get('all_high_confidence_rejected_rows', []))
summary = proof_audit_summary(active)

metrics = st.columns(4)
metrics[0].metric(t('locked_rows'), int(len(active)))
metrics[1].metric(t('rejected_rows'), int(len(rejected)))
metrics[2].metric('Proof quality', f"{summary['proof_quality_score']}/100")
metrics[3].metric('Valid pre-start', int(summary['locked_before_start']))

if not active.empty:
    st.dataframe(active, use_container_width=True, hide_index=True)
    csv_link(t('download'), active, f'all_high_confidence_internal_{workspace_id}.csv')

if not rejected.empty:
    st.subheader(t('rejected'))
    st.dataframe(rejected, use_container_width=True, hide_index=True)

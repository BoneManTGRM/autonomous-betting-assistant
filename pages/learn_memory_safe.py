from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from autonomous_betting_agent.four_tool_orchestrator import page_health_frame
from autonomous_betting_agent.learning import ProbabilityCalibrator, fit_probability_calibrator
from autonomous_betting_agent.learning_memory_tools import (
    build_memory_bank,
    build_segments,
    calibrator_json,
    make_ara_memory_csv,
    memory_metrics,
    merge_dedupe_rows,
    prune_rows,
    read_compact_csv_bytes,
    rows_to_graded,
    valid_bank_row,
)
from autonomous_betting_agent.learning_memory_upload_modes import detect_upload_context
from autonomous_betting_agent.learning_strength import learning_memory_health
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARNED_STATE_PATH = REPO_ROOT / 'learned_state.json'
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'
DEFAULT_REPO = 'BoneManTGRM/autonomous-betting-agent'
DEFAULT_BRANCH = 'main'

st.set_page_config(page_title='Learning Memory', layout='wide')
LANG = render_app_sidebar('learning_memory', language_key='learning_memory_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Learning Memory',
        'caption': 'Durable learning. Real probabilities are full-trust, odds-implied rows are medium-trust, and high-confidence result-only rows are accepted as lower-trust fallback data.',
        'upload': 'Upload graded results CSV',
        'upload_type': 'Upload type',
        'auto': 'Auto-detect',
        'rich': 'Odds / probability-rich file',
        'fallback': 'High-confidence result-only file',
        'fallback_note': 'Fallback rows are accepted, marked, and weighted lower so they help sample size without overpowering better probability data.',
        'train': 'Train and remember',
        'replace': 'Replace old memory with this upload',
        'merge': 'Merge upload with existing memory',
        'save': 'Save learning files back to GitHub',
        'need_upload': 'Upload a graded CSV first.',
        'too_few': 'Not enough usable rows after pruning.',
        'saved_local': 'Learning memory updated locally.',
        'saved_github': 'Learning files saved to GitHub.',
        'save_error': 'GitHub save failed',
        'health': 'Learning health',
        'handoff': 'Training readiness',
        'patterns': 'Top learned patterns',
        'summary': 'Training summary',
        'download': 'Download ARA memory CSV',
        'source_context': 'Detected context',
        'no_usable': 'No usable resolved rows. Try High-confidence result-only mode if this file has results but no probabilities.',
    },
    'es': {
        'title': 'Memoria de Aprendizaje',
        'caption': 'Aprendizaje duradero. Las probabilidades reales tienen confianza completa; las cuotas implícitas tienen confianza media; y los archivos de alta confianza solo con resultados entran como datos fallback de menor peso.',
        'upload': 'Subir CSV de resultados calificados',
        'upload_type': 'Tipo de carga',
        'auto': 'Detectar automáticamente',
        'rich': 'Archivo con cuotas / probabilidades',
        'fallback': 'Archivo de alta confianza solo con resultados',
        'fallback_note': 'Las filas fallback se aceptan, se marcan y pesan menos para ayudar al tamaño de muestra sin dominar datos mejores.',
        'train': 'Entrenar y recordar',
        'replace': 'Reemplazar memoria anterior con esta carga',
        'merge': 'Combinar carga con memoria existente',
        'save': 'Guardar archivos de aprendizaje en GitHub',
        'need_upload': 'Primero sube un CSV calificado.',
        'too_few': 'No hay suficientes filas útiles después de podar.',
        'saved_local': 'Memoria de aprendizaje actualizada localmente.',
        'saved_github': 'Archivos de aprendizaje guardados en GitHub.',
        'save_error': 'Falló el guardado en GitHub',
        'health': 'Salud del aprendizaje',
        'handoff': 'Preparación para entrenamiento',
        'patterns': 'Principales patrones aprendidos',
        'summary': 'Resumen del entrenamiento',
        'download': 'Descargar CSV de memoria ARA',
        'source_context': 'Contexto detectado',
        'no_usable': 'No hay filas resueltas útiles. Prueba el modo de alta confianza si este archivo tiene resultados pero no probabilidades.',
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def secret(*names: str) -> str:
    for name in names:
        try:
            value = str(st.secrets.get(name, '')).strip()
            if value:
                return value
        except Exception:
            pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def load_bank() -> dict[str, Any]:
    try:
        return json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8')) if MEMORY_BANK_PATH.exists() else {'compact_rows': []}
    except Exception:
        return {'compact_rows': []}


def save_github(path: str, content: str, message: str) -> None:
    token = secret('GITHUB_TOKEN', 'GH_TOKEN')
    if not token:
        raise RuntimeError('Missing GitHub token')
    repo = secret('GITHUB_REPOSITORY') or DEFAULT_REPO
    branch = secret('GITHUB_BRANCH') or DEFAULT_BRANCH
    url = f'https://api.github.com/repos/{repo}/contents/{path}'
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    sha = None
    existing = requests.get(url, headers=headers, params={'ref': branch}, timeout=20)
    if existing.status_code == 200:
        sha = existing.json().get('sha')
    body: dict[str, Any] = {'message': message, 'branch': branch, 'content': base64.b64encode(content.encode('utf-8')).decode('ascii')}
    if sha:
        body['sha'] = sha
    response = requests.put(url, headers=headers, json=body, timeout=30)
    if response.status_code not in {200, 201}:
        raise RuntimeError(f'{response.status_code}: {response.text[:300]}')


def show_health(rows: list[dict[str, Any]], title: str) -> None:
    st.subheader(title)
    health = learning_memory_health(rows)
    c = st.columns(6)
    c[0].metric('Score', health.get('learning_health_score'))
    c[1].metric('Tier', str(health.get('learning_health_tier', '')).replace('_', ' '))
    c[2].metric('Resolved', health.get('resolved_rows'))
    c[3].metric('Wins', health.get('wins'))
    c[4].metric('Losses', health.get('losses'))
    c[5].metric('Markets', health.get('market_count'))


st.title(t('title'))
st.caption(t('caption'))

bank = load_bank()
existing_rows = [row for row in (valid_bank_row(row) for row in bank.get('compact_rows', [])) if row]
existing_metrics = memory_metrics(existing_rows)
summary = st.columns(6)
summary[0].metric('Rows', existing_metrics['resolved'])
summary[1].metric('Hit rate', pct(existing_metrics['hit_rate']) if existing_metrics['hit_rate'] is not None else 'N/A')
summary[2].metric('ROI', pct(existing_metrics['roi']) if existing_metrics['roi'] is not None else 'N/A')
summary[3].metric('Profit units', f"{float(existing_metrics.get('profit_units') or 0):.2f}")
summary[4].metric('Avg predicted', pct(existing_metrics['avg_predicted']) if existing_metrics['avg_predicted'] is not None else 'N/A')
summary[5].metric('Bank version', str(bank.get('version', 'unknown')))

if existing_rows:
    show_health(existing_rows, t('health'))

st.subheader(t('upload'))
mode_labels = [t('auto'), t('rich'), t('fallback')]
upload_type_label = st.radio(t('upload_type'), mode_labels, index=0, horizontal=False)
upload_type = 'fallback_high_confidence' if upload_type_label == t('fallback') else 'rich' if upload_type_label == t('rich') else 'auto'
if upload_type == 'fallback_high_confidence':
    st.warning(t('fallback_note'))

uploaded = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=False, key='safe_learning_upload')
uploaded_rows: list[dict[str, Any]] = []
parse_stats: dict[str, Any] = {}
context = ''
if uploaded is not None:
    data = uploaded.getvalue()
    context = detect_upload_context(data, getattr(uploaded, 'name', 'uploaded.csv'), upload_type)
    st.caption(f"{t('source_context')}: {context[:500]}")
    uploaded_rows, parse_stats = read_compact_csv_bytes(data, context)
    cols = st.columns(7)
    cols[0].metric('Input', parse_stats.get('input_rows', 0))
    cols[1].metric('Usable', parse_stats.get('usable_rows', 0))
    cols[2].metric('Wins', parse_stats.get('wins', 0))
    cols[3].metric('Losses', parse_stats.get('losses', 0))
    cols[4].metric('Direct', parse_stats.get('direct_probability_rows', 0))
    cols[5].metric('Odds-implied', parse_stats.get('price_implied_probability_rows', 0))
    cols[6].metric('Fallback', parse_stats.get('fallback_probability_rows', 0))
    if uploaded_rows:
        show_health(uploaded_rows, t('handoff'))
        st.dataframe(pd.DataFrame(uploaded_rows).head(200), use_container_width=True, hide_index=True)
    else:
        st.error(t('no_usable'))

settings = st.columns(4)
min_events = settings[0].number_input('Minimum graded events', min_value=5, max_value=500, value=5, step=1)
max_rows = settings[1].number_input('Max stored rows', min_value=10, max_value=50000, value=10000, step=500)
min_patterns = settings[2].number_input('Min rows per pattern', min_value=2, max_value=50, value=3, step=1)
max_patterns = settings[3].number_input('Max stored patterns', min_value=20, max_value=2000, value=500, step=50)
training_mode_label = st.radio('Training mode', [t('replace'), t('merge')], index=1, horizontal=False)
save_to_github = st.toggle(t('save'), value=bool(secret('GITHUB_TOKEN', 'GH_TOKEN')))

if st.button(t('train'), type='primary', use_container_width=True):
    if uploaded is None:
        st.warning(t('need_upload'))
        st.stop()
    source_rows = [] if training_mode_label == t('replace') else existing_rows
    merged_rows, duplicates_removed = merge_dedupe_rows(source_rows, uploaded_rows)
    pruned_rows, prune_report = prune_rows(merged_rows, int(max_rows))
    if len(pruned_rows) < int(min_events):
        st.error(f"{t('too_few')} Rows={len(pruned_rows)} Need={int(min_events)}")
        st.stop()
    calibrator = fit_probability_calibrator(rows_to_graded(pruned_rows), min_events=int(min_events), source=getattr(uploaded, 'name', 'uploaded.csv'))
    segments = build_segments(pruned_rows, int(min_patterns), int(max_patterns))
    ara_csv = make_ara_memory_csv(segments)
    memory_bank = build_memory_bank(compact_rows=pruned_rows, calibrator=calibrator, segments=segments, parse_stats=parse_stats, prune_report=prune_report, mode='replace' if training_mode_label == t('replace') else 'merge', existing_count=len(existing_rows), uploaded_count=len(uploaded_rows), duplicates_removed=duplicates_removed)
    memory_bank['summary']['upload_type'] = upload_type
    memory_bank['summary']['source_context'] = context[:500]
    MEMORY_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_BANK_PATH.write_text(json.dumps(memory_bank, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    LEARNED_STATE_PATH.write_text(calibrator_json(calibrator), encoding='utf-8')
    ARA_MEMORY_PATH.write_text(ara_csv, encoding='utf-8')
    st.success(t('saved_local'))
    if save_to_github:
        try:
            today = datetime.now(timezone.utc).date().isoformat()
            save_github('learned_state.json', calibrator_json(calibrator), f'Update learned calibration {today}')
            save_github('data/learning_memory_bank.json', json.dumps(memory_bank, indent=2, sort_keys=True) + '\n', f'Update cumulative learning memory {today}')
            save_github('data/ara_learning_memory.csv', ara_csv, f'Update ARA memory patterns {today}')
            st.success(t('saved_github'))
        except Exception as exc:
            st.error(f"{t('save_error')}: {exc}")
    st.subheader(t('summary'))
    st.json(memory_bank['summary'])
    st.subheader(t('patterns'))
    st.dataframe(pd.DataFrame(segments[:100]), use_container_width=True, hide_index=True)
    st.download_button(t('download'), ara_csv, file_name='ara_learning_memory.csv', mime='text/csv')

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
from autonomous_betting_agent.learning_strength import learning_memory_health
from autonomous_betting_agent.ui_language import render_language_selector

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARNED_STATE_PATH = REPO_ROOT / 'learned_state.json'
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'
DEFAULT_GITHUB_REPOSITORY = 'BoneManTGRM/autonomous-betting-agent'
DEFAULT_GITHUB_BRANCH = 'main'

st.set_page_config(page_title='Memoria de Aprendizaje', layout='wide')
LANG = render_language_selector(key='learning_memory_language')

TEXT = {
    'en': {
        'title': 'Learning Memory',
        'caption': 'Durable training page. It reviews usable finished rows, audits memory health, trains calibration, saves cumulative memory, and exports ARA pattern memory.',
        'workflow': 'Clean path: Pro Predictor → What Are the Odds → Learning Memory.',
        'source_truth': 'Learning source of truth',
        'saved_calibration': 'Saved calibration',
        'cumulative': 'Cumulative memory',
        'health': 'Learning health',
        'handoff': 'Training handoff readiness',
        'upload': 'Upload graded results CSV',
        'preview': 'Upload preview',
        'train': 'Train and remember',
        'replace': 'Replace old memory with this upload',
        'merge': 'Merge upload with existing memory',
        'min_events': 'Minimum graded events',
        'max_rows': 'Max stored rows',
        'min_patterns': 'Min rows per pattern',
        'max_patterns': 'Max stored patterns',
        'save': 'Save learning files back to GitHub',
        'missing_token': 'GitHub saving is enabled, but GITHUB_TOKEN is missing.',
        'need_upload': 'Upload a graded CSV first.',
        'too_few': 'Not enough usable rows after pruning.',
        'saved_local': 'Learning memory updated locally for this running app session.',
        'saved_github': 'Saved learned_state.json, cumulative memory, and ARA memory patterns to GitHub.',
        'save_error': 'GitHub save failed',
        'patterns': 'Top learned patterns',
        'download_patterns': 'Download ARA memory CSV',
        'explain_title': 'What the memory is learning',
        'explain_body': 'The memory learns from finished, graded picks. It compares the model probability against the real outcome, then records where the system was overconfident, underconfident, or accurate. It groups those lessons by sport, market, probability bucket, bookmaker, confidence tier, number of books, and API coverage. Future runs can use these patterns to raise trust, lower trust, or require review before a pick is promoted.',
        'why_works_title': 'Why this works',
        'why_works_body': 'It works because it does not train on opinions. It trains on prediction versus result. If 65% picks in one market only win 52%, the system learns that pattern is overconfident. If another group wins more often than expected, it can increase confidence carefully. The larger and more balanced the sample, the stronger this memory becomes.',
        'how_used_title': 'How it is used',
        'how_used_body': 'The saved files are used as calibration and pattern memory. learned_state.json stores global calibration. learning_memory_bank.json stores compact finished rows. ara_learning_memory.csv stores grouped patterns that ARA can scan later when ranking future picks.',
        'events_explain': 'Learned events are finished rows used for training. They are not future picks. They are the examples the system studies to compare probability, price/context, and final result.',
        'metric_health': 'Health',
        'metric_tier': 'Tier',
        'metric_resolved': 'Resolved',
        'metric_wins': 'Wins',
        'metric_losses': 'Losses',
        'metric_real_probs': 'Real probs',
        'metric_markets': 'Markets',
        'events': 'Events',
        'raw_accuracy': 'Raw accuracy',
        'calibrated_accuracy': 'Calibrated accuracy',
        'brier_after': 'Brier after',
        'hit_rate': 'Hit rate',
        'avg_predicted': 'Avg predicted',
        'training_mode': 'Training mode',
        'training_summary': 'Training summary',
        'final_health': 'Final trained memory health',
        'final_handoff': 'Final training handoff readiness',
        'upload_health': 'Upload health',
        'upload_handoff': 'Upload handoff readiness',
        'no_state': 'No learned_state.json loaded.',
        'no_usable': 'This CSV has no usable resolved rows.',
    },
    'es': {
        'title': 'Memoria de Aprendizaje',
        'caption': 'Página de entrenamiento duradero. Revisa filas finalizadas útiles, audita salud de memoria, entrena calibración, guarda memoria acumulativa y exporta patrones ARA.',
        'workflow': 'Ruta limpia: Predictor Pro → ¿Cuáles Son las Cuotas? → Memoria de Aprendizaje.',
        'source_truth': 'Fuente única de aprendizaje',
        'saved_calibration': 'Calibración guardada',
        'cumulative': 'Memoria acumulativa',
        'health': 'Salud del aprendizaje',
        'handoff': 'Preparación para entrenamiento',
        'upload': 'Subir CSV de resultados calificados',
        'preview': 'Vista previa de carga',
        'train': 'Entrenar y recordar',
        'replace': 'Reemplazar memoria anterior con esta carga',
        'merge': 'Combinar carga con memoria existente',
        'min_events': 'Mínimo de eventos calificados',
        'max_rows': 'Máximo de filas guardadas',
        'min_patterns': 'Mínimo de filas por patrón',
        'max_patterns': 'Máximo de patrones guardados',
        'save': 'Guardar archivos de aprendizaje en GitHub',
        'missing_token': 'Guardar en GitHub está activado, pero falta GITHUB_TOKEN.',
        'need_upload': 'Primero sube un CSV calificado.',
        'too_few': 'No hay suficientes filas útiles después de podar.',
        'saved_local': 'Memoria de aprendizaje actualizada localmente en esta sesión.',
        'saved_github': 'Se guardaron learned_state.json, memoria acumulativa y patrones ARA en GitHub.',
        'save_error': 'Falló el guardado en GitHub',
        'patterns': 'Principales patrones aprendidos',
        'download_patterns': 'Descargar CSV de memoria ARA',
        'explain_title': 'Qué está aprendiendo la memoria',
        'explain_body': 'La memoria aprende de picks terminados y calificados. Compara la probabilidad del modelo contra el resultado real, y guarda dónde el sistema fue demasiado confiado, poco confiado o acertado. Agrupa esas lecciones por deporte, mercado, rango de probabilidad, casa de apuestas, nivel de confianza, número de casas y cobertura de APIs. En futuras corridas, esos patrones ayudan a subir confianza, bajar confianza o exigir revisión antes de promover un pick.',
        'why_works_title': 'Por qué funciona',
        'why_works_body': 'Funciona porque no entrena con opiniones. Entrena con predicción contra resultado. Si picks de 65% en un mercado solo ganan 52%, el sistema aprende que ese patrón está sobreconfiado. Si otro grupo gana más de lo esperado, puede aumentar confianza con cuidado. Mientras más grande y balanceada sea la muestra, más fuerte se vuelve esta memoria.',
        'how_used_title': 'Cómo se usa',
        'how_used_body': 'Los archivos guardados se usan como calibración y memoria de patrones. learned_state.json guarda la calibración global. learning_memory_bank.json guarda filas compactas finalizadas. ara_learning_memory.csv guarda patrones agrupados que ARA puede revisar después al ordenar picks futuros.',
        'events_explain': 'Eventos aprendidos son filas terminadas usadas para entrenamiento. No son picks futuros. Son ejemplos que el sistema estudia para comparar probabilidad, precio/contexto y resultado final.',
        'metric_health': 'Salud',
        'metric_tier': 'Nivel',
        'metric_resolved': 'Resueltos',
        'metric_wins': 'Victorias',
        'metric_losses': 'Derrotas',
        'metric_real_probs': 'Probs reales',
        'metric_markets': 'Mercados',
        'events': 'Eventos',
        'raw_accuracy': 'Precisión bruta',
        'calibrated_accuracy': 'Precisión calibrada',
        'brier_after': 'Brier después',
        'hit_rate': 'Win rate',
        'avg_predicted': 'Promedio predicho',
        'training_mode': 'Modo de entrenamiento',
        'training_summary': 'Resumen del entrenamiento',
        'final_health': 'Salud final de la memoria entrenada',
        'final_handoff': 'Preparación final de entrenamiento',
        'upload_health': 'Salud de la carga',
        'upload_handoff': 'Preparación de carga',
        'no_state': 'No se cargó learned_state.json.',
        'no_usable': 'Este CSV no tiene filas resueltas útiles.',
    },
}

HEALTH_TRANSLATIONS = {
    'en': {
        'strong_learning_memory': 'Strong',
        'usable_learning_memory': 'Usable',
        'rough_learning_memory': 'Rough',
        'not_ready': 'Not ready',
        'train_and_use_for_calibration': 'Use for calibration',
        'train_but_keep_sample_warning': 'Use with sample warning',
        'train_for_rough_patterns_only': 'Rough patterns only',
        'collect_more_finished_results': 'Collect more finished results',
        'large_sample': 'large sample',
        'serious_sample': 'serious sample',
        'starter_sample': 'starter sample',
        'tiny_sample': 'tiny sample',
        'not_enough_resolved_rows': 'not enough resolved rows',
        'good_probability_coverage': 'good probability coverage',
        'needs_more_real_probabilities': 'needs more real probabilities',
        'has_wins_and_losses': 'has wins and losses',
        'class_balance_weak': 'class balance weak',
        'multi_sport_memory': 'multi-sport memory',
        'some_sport_diversity': 'some sport diversity',
        'limited_sport_diversity': 'limited sport diversity',
        'multi_market_memory': 'multi-market memory',
        'limited_market_diversity': 'limited market diversity',
    },
    'es': {
        'strong_learning_memory': 'Fuerte',
        'usable_learning_memory': 'Utilizable',
        'rough_learning_memory': 'Inicial',
        'not_ready': 'No lista',
        'train_and_use_for_calibration': 'Usar para calibración',
        'train_but_keep_sample_warning': 'Usar con aviso de muestra',
        'train_for_rough_patterns_only': 'Solo patrones iniciales',
        'collect_more_finished_results': 'Recolectar más resultados finales',
        'large_sample': 'muestra grande',
        'serious_sample': 'muestra seria',
        'starter_sample': 'muestra inicial',
        'tiny_sample': 'muestra pequeña',
        'not_enough_resolved_rows': 'faltan filas resueltas',
        'good_probability_coverage': 'buena cobertura de probabilidad',
        'needs_more_real_probabilities': 'faltan más probabilidades reales',
        'has_wins_and_losses': 'tiene victorias y derrotas',
        'class_balance_weak': 'balance débil de wins/losses',
        'multi_sport_memory': 'memoria multi-deporte',
        'some_sport_diversity': 'algo de diversidad deportiva',
        'limited_sport_diversity': 'diversidad deportiva limitada',
        'multi_market_memory': 'memoria multi-mercado',
        'limited_market_diversity': 'diversidad de mercado limitada',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def tr(value: Any) -> str:
    text = str(value or '').strip()
    return HEALTH_TRANSLATIONS.get(LANG, {}).get(text, text.replace('_', ' '))


def tr_notes(notes: Any) -> str:
    parts = [part.strip() for part in str(notes or '').split('|') if part.strip()]
    return ' | '.join(tr(part) for part in parts)


def pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


def get_secret(*names: str) -> str:
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


def load_memory_bank() -> dict[str, Any]:
    try:
        if MEMORY_BANK_PATH.exists():
            return json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {'version': 'learning-memory-bank-v1', 'compact_rows': []}


def current_learned_state() -> ProbabilityCalibrator | None:
    try:
        if LEARNED_STATE_PATH.exists():
            return ProbabilityCalibrator.load(LEARNED_STATE_PATH)
    except Exception:
        return None
    return None


def github_put_text_file(*, path: str, content: str, message: str) -> None:
    token = get_secret('GITHUB_TOKEN', 'GH_TOKEN')
    if not token:
        raise RuntimeError('Missing GITHUB_TOKEN in Streamlit secrets.')
    repository = get_secret('GITHUB_REPOSITORY') or DEFAULT_GITHUB_REPOSITORY
    branch = get_secret('GITHUB_BRANCH') or DEFAULT_GITHUB_BRANCH
    url = f'https://api.github.com/repos/{repository}/contents/{path}'
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    sha = None
    read_response = requests.get(url, headers=headers, params={'ref': branch}, timeout=20)
    if read_response.status_code == 200:
        sha = read_response.json().get('sha')
    elif read_response.status_code != 404:
        raise RuntimeError(f'GitHub read failed: {read_response.status_code} {read_response.text[:500]}')
    payload: dict[str, Any] = {'message': message, 'content': base64.b64encode(content.encode('utf-8')).decode('ascii'), 'branch': branch}
    if sha:
        payload['sha'] = sha
    write_response = requests.put(url, headers=headers, json=payload, timeout=20)
    if write_response.status_code not in (200, 201):
        raise RuntimeError(f'GitHub write failed: {write_response.status_code} {write_response.text[:500]}')


def health_badge(health: dict[str, Any]) -> None:
    tier = str(health.get('learning_health_tier', 'not_ready'))
    action = str(health.get('recommended_learning_action', 'collect_more_finished_results'))
    message = f"{tr(tier)} | {tr(action)} | {tr_notes(health.get('health_notes', ''))}"
    if tier == 'strong_learning_memory':
        st.success(message)
    elif tier == 'usable_learning_memory':
        st.info(message)
    elif tier == 'rough_learning_memory':
        st.warning(message)
    else:
        st.error(message)


def show_learning_explainer() -> None:
    with st.expander(t('explain_title'), expanded=True):
        st.write(t('explain_body'))
        st.write(f"**{t('why_works_title')}:** {t('why_works_body')}")
        st.write(f"**{t('how_used_title')}:** {t('how_used_body')}")
        st.caption(t('events_explain'))


def show_health(rows: list[dict[str, Any]], title: str) -> dict[str, Any]:
    health = learning_memory_health(rows)
    st.subheader(title)
    cols = st.columns(7)
    cols[0].metric(t('metric_health'), health['learning_health_score'])
    cols[1].metric(t('metric_tier'), tr(health['learning_health_tier']))
    cols[2].metric(t('metric_resolved'), health['resolved_rows'])
    cols[3].metric(t('metric_wins'), health['wins'])
    cols[4].metric(t('metric_losses'), health['losses'])
    cols[5].metric(t('metric_real_probs'), health['real_probability_rows'])
    cols[6].metric(t('metric_markets'), health['market_count'])
    health_badge(health)
    return health


def show_handoff(rows: list[dict[str, Any]], title: str) -> None:
    st.subheader(title)
    st.dataframe(page_health_frame(pd.DataFrame(rows), page='learning_memory'), use_container_width=True, hide_index=True)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('workflow'))
show_learning_explainer()

current = current_learned_state()
bank = load_memory_bank()
existing_rows = [row for row in (valid_bank_row(row) for row in bank.get('compact_rows', [])) if row is not None]
existing_metrics = memory_metrics(existing_rows)
existing_segments = build_segments(existing_rows, 3, 200) if existing_rows else []

with st.expander(t('source_truth'), expanded=False):
    truth = st.columns(4)
    truth[0].metric('learned_state.json', 'Loaded' if current is not None else 'Missing')
    truth[1].metric('learning_memory_bank.json', f'{len(existing_rows)} rows')
    truth[2].metric('ara_learning_memory.csv', 'Ready' if existing_segments else 'No patterns')
    truth[3].metric('Bank version', str(bank.get('version', 'unknown')))

st.subheader(t('saved_calibration'))
cal = st.columns(4)
if current is not None:
    cal[0].metric(t('events'), current.events_trained, help=t('events_explain'))
    cal[1].metric(t('raw_accuracy'), pct(current.accuracy_before))
    cal[2].metric(t('calibrated_accuracy'), pct(current.accuracy_after))
    cal[3].metric(t('brier_after'), 'N/A' if current.brier_after is None else f'{current.brier_after:.4f}')
else:
    st.warning(t('no_state'))

st.subheader(t('cumulative'))
summary_cols = st.columns(6)
summary_cols[0].metric(t('metric_resolved'), existing_metrics['resolved'], help=t('events_explain'))
summary_cols[1].metric(t('hit_rate'), pct(existing_metrics['hit_rate']) if existing_metrics['hit_rate'] is not None else 'N/A')
summary_cols[2].metric(t('avg_predicted'), pct(existing_metrics['avg_predicted']) if existing_metrics['avg_predicted'] is not None else 'N/A')
summary_cols[3].metric('Brier', 'N/A' if existing_metrics['brier'] is None else f"{float(existing_metrics['brier']):.4f}")
summary_cols[4].metric(t('metric_wins'), existing_metrics['wins'])
summary_cols[5].metric(t('metric_losses'), existing_metrics['losses'])
show_health(existing_rows, t('health'))
show_handoff(existing_rows, t('handoff'))

if existing_segments:
    st.subheader(t('patterns'))
    st.caption(t('explain_body'))
    st.dataframe(pd.DataFrame(existing_segments[:40]), use_container_width=True, hide_index=True)

st.subheader(t('upload'))
graded_upload = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=False, key='graded_results_for_learning_memory')
uploaded_rows: list[dict[str, Any]] = []
parse_stats: dict[str, Any] = {}
if graded_upload is not None:
    uploaded_rows, parse_stats = read_compact_csv_bytes(graded_upload.getvalue(), getattr(graded_upload, 'name', 'uploaded_graded_results.csv'))
    st.subheader(t('preview'))
    pcols = st.columns(8)
    pcols[0].metric('Input', parse_stats.get('input_rows', 0))
    pcols[1].metric('Usable', parse_stats.get('usable_rows', 0))
    pcols[2].metric(t('metric_wins'), parse_stats.get('wins', 0))
    pcols[3].metric(t('metric_losses'), parse_stats.get('losses', 0))
    pcols[4].metric('Direct probs', parse_stats.get('direct_probability_rows', 0))
    pcols[5].metric('Price-implied', parse_stats.get('price_implied_probability_rows', 0))
    pcols[6].metric('Fallback', parse_stats.get('fallback_probability_rows', 0))
    pcols[7].metric('Missing result', parse_stats.get('missing_result', 0))
    show_health(uploaded_rows, t('upload_health'))
    show_handoff(uploaded_rows, t('upload_handoff'))
    if uploaded_rows:
        st.dataframe(pd.DataFrame(uploaded_rows).head(100), use_container_width=True, hide_index=True)
    else:
        st.error(t('no_usable'))

settings = st.columns(4)
min_events = settings[0].number_input(t('min_events'), min_value=5, max_value=500, value=5, step=1)
max_rows = settings[1].number_input(t('max_rows'), min_value=10, max_value=10000, value=2500, step=100)
min_segment_records = settings[2].number_input(t('min_patterns'), min_value=2, max_value=50, value=3, step=1)
max_segments = settings[3].number_input(t('max_patterns'), min_value=20, max_value=1000, value=200, step=20)
training_mode = st.radio(t('training_mode'), [t('replace'), t('merge')], index=0, horizontal=False)
save_to_github = st.toggle(t('save'), value=bool(get_secret('GITHUB_TOKEN', 'GH_TOKEN')))
if save_to_github and not get_secret('GITHUB_TOKEN', 'GH_TOKEN'):
    st.warning(t('missing_token'))

if st.button(t('train'), type='primary', use_container_width=True):
    if graded_upload is None:
        st.warning(t('need_upload'))
        st.stop()
    source_rows = [] if training_mode == t('replace') else existing_rows
    merged_rows, duplicates_removed = merge_dedupe_rows(source_rows, uploaded_rows)
    pruned_rows, prune_report = prune_rows(merged_rows, int(max_rows))
    if len(pruned_rows) < int(min_events):
        st.error(f"{t('too_few')} Rows={len(pruned_rows)} Need={int(min_events)}")
        st.stop()
    graded_rows = rows_to_graded(pruned_rows)
    calibrator = fit_probability_calibrator(graded_rows, min_events=int(min_events), source=getattr(graded_upload, 'name', 'uploaded_graded_results.csv'))
    mode_name = 'replace' if training_mode == t('replace') else 'merge'
    calibrator.notes.append(f'Mode={mode_name}. Existing rows used={len(source_rows)}. Uploaded usable rows={len(uploaded_rows)}. Duplicates removed={duplicates_removed}. Trained on {len(pruned_rows)} rows.')
    segments = build_segments(pruned_rows, int(min_segment_records), int(max_segments))
    ara_csv = make_ara_memory_csv(segments)
    memory_bank = build_memory_bank(compact_rows=pruned_rows, calibrator=calibrator, segments=segments, parse_stats=parse_stats, prune_report=prune_report, mode=mode_name, existing_count=len(existing_rows), uploaded_count=len(uploaded_rows), duplicates_removed=duplicates_removed)
    MEMORY_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_BANK_PATH.write_text(json.dumps(memory_bank, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    LEARNED_STATE_PATH.write_text(calibrator_json(calibrator), encoding='utf-8')
    ARA_MEMORY_PATH.write_text(ara_csv, encoding='utf-8')
    st.success(t('saved_local'))
    if save_to_github:
        try:
            today = datetime.now(timezone.utc).date().isoformat()
            github_put_text_file(path='learned_state.json', content=calibrator_json(calibrator), message=f'Update learned calibration {today}')
            github_put_text_file(path='data/learning_memory_bank.json', content=json.dumps(memory_bank, indent=2, sort_keys=True) + '\n', message=f'Update cumulative learning memory {today}')
            github_put_text_file(path='data/ara_learning_memory.csv', content=ara_csv, message=f'Update ARA memory patterns {today}')
            st.success(t('saved_github'))
        except Exception as exc:
            st.error(f"{t('save_error')}: {exc}")
    st.subheader(t('training_summary'))
    st.json(memory_bank['summary'])
    show_health(pruned_rows, t('final_health'))
    show_handoff(pruned_rows, t('final_handoff'))
    st.subheader(t('patterns'))
    segments_frame = pd.DataFrame(segments[:60])
    st.dataframe(segments_frame, use_container_width=True, hide_index=True)
    st.download_button(t('download_patterns'), ara_csv, file_name='ara_learning_memory.csv', mime='text/csv')

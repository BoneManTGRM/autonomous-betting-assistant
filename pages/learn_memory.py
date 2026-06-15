from __future__ import annotations

import base64
import builtins
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

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


def get_secret(*names: str) -> str:
    for name in names:
        if not name:
            continue
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


builtins.get_secret = get_secret

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARNED_STATE_PATH = REPO_ROOT / 'learned_state.json'
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'
DEFAULT_GITHUB_REPOSITORY = 'BoneManTGRM/autonomous-betting-agent'
DEFAULT_GITHUB_BRANCH = 'main'

TEXT = {
    'en': {
        'title': 'Learning Memory',
        'caption': 'The single source-of-truth training page. Upload graded results, preview exactly what the trainer can use, replace or merge memory, rebuild calibration, and save it back to GitHub.',
        'single_source': 'Use this page for actual learning/training. The old Self Learning Engine page was removed because it duplicated this workflow and did not save durable learning memory.',
        'workflow_note': 'Recommended path: Agent Decision Engine → Odds Lock → results grading → Learning Memory → Max Agent Intelligence → Proof Readiness.',
        'saved_calibration': 'Saved calibration summary',
        'cumulative_summary': 'Cumulative memory summary',
        'metrics_note': 'Saved calibration is the trained file. Cumulative memory is the raw stored graded rows. Upload preview below shows whether your new CSV is actually usable before training.',
        'source_of_truth': 'Learning source of truth',
        'memory_status': 'Memory status',
        'ready_to_train': 'Ready to train',
        'not_ready_to_train': 'Not ready to train',
        'durable_memory': 'Durable memory files',
        'events_trained': 'Events trained',
        'raw_accuracy': 'Raw accuracy',
        'calibrated_accuracy': 'Calibrated accuracy',
        'brier_after': 'Brier after',
        'resolved_picks': 'Resolved picks',
        'hit_rate': 'Hit rate',
        'avg_predicted': 'Avg predicted',
        'brier_score': 'Brier score',
        'existing_rows': 'Existing cumulative memory rows',
        'wins': 'Wins',
        'losses': 'Losses',
        'metric_mismatch': 'Saved calibration and cumulative memory do not match. Train with the latest graded CSV and save to GitHub so both sections use the same rows.',
        'metric_match': 'Saved calibration and cumulative memory are aligned.',
        'saved_implies': 'Saved calibration implies',
        'memory_shows': 'cumulative memory shows',
        'best_area': 'Best reliable area',
        'weakest_area': 'Weakest reliable area',
        'records': 'records',
        'actual': 'actual',
        'smoothed': 'smoothed',
        'what_learned': 'What ARA learned',
        'train_from_finished': 'Train from finished games',
        'upload_graded': 'Upload graded results CSV',
        'upload_preview': 'Uploaded CSV preview',
        'training_mode': 'Training mode',
        'replace': 'Replace old memory with this upload',
        'merge': 'Merge upload with existing memory',
        'min_events': 'Minimum graded events',
        'max_rows': 'Max stored memory rows',
        'min_pattern_rows': 'Min rows per pattern',
        'max_patterns': 'Max stored patterns',
        'save_github': 'Save learning files back to GitHub so the app remembers after restart',
        'missing_token': 'GitHub saving is enabled, but GITHUB_TOKEN is missing from Streamlit secrets.',
        'button': 'Train and remember',
        'upload_first': 'Upload a graded results CSV first.',
        'too_few': 'Found {rows} usable unique graded rows after pruning. Need at least {needed}.',
        'updated_local': 'Learning memory updated locally for this running app session.',
        'saved_github': 'Saved learned_state.json, cumulative memory, and ARA memory patterns to GitHub.',
        'save_error': 'Could not save all learning files to GitHub: {error}',
        'training_summary': 'Training summary',
        'calibration_details': 'Calibration details',
        'top_patterns': 'Top learned patterns',
        'download_ara': 'Download ARA memory CSV',
        'no_state': 'No learned_state.json is currently loaded.',
        'fallback_note': 'Some rows used a fallback probability because the CSV had results but no probability/odds column. This is acceptable for rough learning, but stronger proof needs real probabilities and odds.',
    },
    'es': {
        'title': 'Memoria de Aprendizaje',
        'caption': 'La página única de entrenamiento. Sube resultados calificados, revisa exactamente qué puede usar el entrenador, reemplaza o combina memoria, reconstruye la calibración y guarda en GitHub.',
        'single_source': 'Usa esta página para aprendizaje/entrenamiento real. La página antigua Self Learning Engine fue eliminada porque duplicaba este flujo y no guardaba memoria duradera.',
        'workflow_note': 'Ruta recomendada: Agent Decision Engine → Odds Lock → calificación de resultados → Memoria de Aprendizaje → Max Agent Intelligence → Proof Readiness.',
        'saved_calibration': 'Resumen de calibración guardado',
        'cumulative_summary': 'Resumen de memoria acumulativa',
        'metrics_note': 'La calibración guardada es el archivo entrenado. La memoria acumulativa son las filas crudas guardadas. La vista previa muestra si el nuevo CSV sirve antes de entrenar.',
        'source_of_truth': 'Fuente única de aprendizaje',
        'memory_status': 'Estado de memoria',
        'ready_to_train': 'Listo para entrenar',
        'not_ready_to_train': 'No listo para entrenar',
        'durable_memory': 'Archivos de memoria duradera',
        'events_trained': 'Eventos entrenados',
        'raw_accuracy': 'Precisión bruta',
        'calibrated_accuracy': 'Precisión calibrada',
        'brier_after': 'Brier después',
        'resolved_picks': 'Pronósticos resueltos',
        'hit_rate': 'Tasa de acierto',
        'avg_predicted': 'Promedio pronosticado',
        'brier_score': 'Puntaje Brier',
        'existing_rows': 'Filas acumuladas en memoria',
        'wins': 'Ganadas',
        'losses': 'Perdidas',
        'metric_mismatch': 'La calibración guardada y la memoria acumulativa no coinciden. Entrena con el CSV calificado más reciente y guarda en GitHub.',
        'metric_match': 'La calibración guardada y la memoria acumulativa están alineadas.',
        'saved_implies': 'La calibración guardada implica',
        'memory_shows': 'la memoria acumulativa muestra',
        'best_area': 'Mejor área confiable',
        'weakest_area': 'Área confiable más débil',
        'records': 'registros',
        'actual': 'real',
        'smoothed': 'suavizado',
        'what_learned': 'Lo que ARA aprendió',
        'train_from_finished': 'Entrenar con partidos terminados',
        'upload_graded': 'Subir CSV de resultados calificados',
        'upload_preview': 'Vista previa del CSV subido',
        'training_mode': 'Modo de entrenamiento',
        'replace': 'Reemplazar memoria anterior con esta carga',
        'merge': 'Combinar carga con memoria existente',
        'min_events': 'Mínimo de eventos calificados',
        'max_rows': 'Máximo de filas guardadas',
        'min_pattern_rows': 'Mínimo de filas por patrón',
        'max_patterns': 'Máximo de patrones guardados',
        'save_github': 'Guardar archivos de aprendizaje en GitHub para recordar después de reiniciar',
        'missing_token': 'Guardar en GitHub está activado, pero falta GITHUB_TOKEN en secretos.',
        'button': 'Entrenar y recordar',
        'upload_first': 'Primero sube un CSV de resultados calificados.',
        'too_few': 'Se encontraron {rows} filas únicas utilizables después de podar. Se necesitan al menos {needed}.',
        'updated_local': 'Memoria de aprendizaje actualizada localmente en esta sesión.',
        'saved_github': 'Se guardaron learned_state.json, memoria acumulativa y patrones ARA en GitHub.',
        'save_error': 'No se pudieron guardar todos los archivos en GitHub: {error}',
        'training_summary': 'Resumen del entrenamiento',
        'calibration_details': 'Detalles de calibración',
        'top_patterns': 'Principales patrones aprendidos',
        'download_ara': 'Descargar CSV de memoria ARA',
        'no_state': 'Actualmente no hay learned_state.json cargado.',
        'fallback_note': 'Algunas filas usaron probabilidad estimada porque el CSV tenía resultados pero no probabilidad/cuotas. Sirve para aprendizaje aproximado; para prueba fuerte se necesitan probabilidades y cuotas reales.',
    },
}

SPANISH_COLUMNS = {
    'area': 'area',
    'area_type': 'tipo_area',
    'group_value': 'valor_grupo',
    'records': 'registros',
    'avg_predicted': 'promedio_pronosticado',
    'actual_hit_rate': 'tasa_acierto_real',
    'actual_minus_predicted': 'real_menos_pronosticado',
    'smoothed_hit_rate': 'tasa_suavizada',
    'smoothed_edge': 'ventaja_suavizada',
    'reliability': 'confiabilidad',
    'brier': 'brier',
    'memory_type': 'tipo_memoria',
    'importance': 'importancia',
    'action': 'accion',
}

st.set_page_config(page_title='Learning Memory', layout='wide')
language_choice = st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='learning_memory_language')
LANG = 'es' if language_choice == 'Español' else 'en'


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: float | None) -> str:
    return '' if value is None else f'{value * 100:.1f}%'


def display_segments(rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if frame.empty or LANG != 'es':
        return frame
    return frame.rename(columns={col: SPANISH_COLUMNS.get(str(col), str(col)) for col in frame.columns})


def summary_for_display(summary: dict[str, Any]) -> dict[str, Any]:
    if LANG != 'es':
        return summary
    names = {
        'existing_rows_before_upload': 'filas_existentes_antes_de_subir',
        'uploaded_usable_rows': 'filas_subidas_utilizables',
        'duplicates_removed': 'duplicados_eliminados',
        'rows_after_pruning': 'filas_despues_de_poda',
        'patterns_saved': 'patrones_guardados',
        'fallback_probability_rows': 'filas_con_probabilidad_estimada',
    }
    return {names.get(key, key): value for key, value in summary.items()}


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


def github_put_text_file(*, path: str, content: str, message: str) -> dict[str, Any]:
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
    return write_response.json()


def area_line(label: str, segment: dict[str, Any]) -> str:
    return f"{label}: {segment.get('area')} | {segment.get('records')} {t('records')} | {float(segment.get('actual_hit_rate', 0)):.1%} {t('actual')} | {float(segment.get('smoothed_hit_rate', 0)):.1%} {t('smoothed')}"


st.title(t('title'))
st.caption(t('caption'))
st.info(t('single_source'))
st.caption(t('workflow_note'))

current = current_learned_state()
bank = load_memory_bank()
existing_rows = [row for row in (valid_bank_row(row) for row in bank.get('compact_rows', [])) if row is not None]
existing_metrics = memory_metrics(existing_rows)
existing_segments = build_segments(existing_rows, 3, 160) if existing_rows else []

st.subheader(t('source_of_truth'))
st.caption(t('durable_memory'))
truth_cols = st.columns(4)
truth_cols[0].metric('learned_state.json', 'Loaded' if current is not None else 'Missing')
truth_cols[1].metric('learning_memory_bank.json', f"{len(existing_rows)} rows")
truth_cols[2].metric('ara_learning_memory.csv', 'Generated patterns')
truth_cols[3].metric(t('memory_status'), t('ready_to_train') if len(existing_rows) >= 5 else t('not_ready_to_train'))

st.subheader(t('saved_calibration'))
saved_raw_wins = None
if current is not None:
    cols = st.columns(4)
    cols[0].metric(t('events_trained'), current.events_trained)
    cols[1].metric(t('raw_accuracy'), '' if current.accuracy_before is None else pct(current.accuracy_before))
    cols[2].metric(t('calibrated_accuracy'), '' if current.accuracy_after is None else pct(current.accuracy_after))
    cols[3].metric(t('brier_after'), '' if current.brier_after is None else f'{current.brier_after:.4f}')
    if current.accuracy_before is not None:
        saved_raw_wins = int(round(float(current.accuracy_before) * int(current.events_trained)))
else:
    st.info(t('no_state'))

st.subheader(t('cumulative_summary'))
st.caption(t('metrics_note'))
cols = st.columns(4)
cols[0].metric(t('resolved_picks'), existing_metrics['resolved'])
cols[1].metric(t('hit_rate'), pct(existing_metrics['hit_rate']) if existing_metrics['hit_rate'] is not None else '')
cols[2].metric(t('avg_predicted'), pct(existing_metrics['avg_predicted']) if existing_metrics['avg_predicted'] is not None else '')
cols[3].metric(t('brier_score'), '' if existing_metrics['brier'] is None else f"{float(existing_metrics['brier']):.4f}")
win_cols = st.columns(3)
win_cols[0].metric(t('existing_rows'), len(existing_rows))
win_cols[1].metric(t('wins'), existing_metrics['wins'])
win_cols[2].metric(t('losses'), existing_metrics['losses'])

if current is not None and saved_raw_wins is not None and int(current.events_trained) == int(existing_metrics['resolved']):
    memory_wins = int(existing_metrics['wins'] or 0)
    if saved_raw_wins != memory_wins:
        st.warning(f"{t('metric_mismatch')} {t('saved_implies')} {saved_raw_wins} {t('wins').lower()}; {t('memory_shows')} {memory_wins} {t('wins').lower()}.")
    else:
        st.success(t('metric_match'))

if existing_segments:
    best = max(existing_segments, key=lambda row: (float(row.get('reliability', 0)), float(row.get('smoothed_edge', 0))))
    weakest = min(existing_segments, key=lambda row: (float(row.get('reliability', 0)), float(row.get('smoothed_edge', 0))))
    st.success(area_line(t('best_area'), best))
    st.warning(area_line(t('weakest_area'), weakest))
    with st.expander(t('what_learned'), expanded=False):
        st.dataframe(display_segments(existing_segments[:40]), use_container_width=True, hide_index=True)

st.subheader(t('train_from_finished'))
graded_upload = st.file_uploader(t('upload_graded'), type=['csv'], accept_multiple_files=False, key='graded_results_for_learning_memory')

uploaded_rows: list[dict[str, Any]] = []
parse_stats: dict[str, Any] = {}
if graded_upload is not None:
    uploaded_bytes = graded_upload.getvalue()
    uploaded_rows, parse_stats = read_compact_csv_bytes(uploaded_bytes, getattr(graded_upload, 'name', 'uploaded_graded_results.csv'))
    st.subheader(t('upload_preview'))
    pcols = st.columns(7)
    pcols[0].metric('Input rows', parse_stats.get('input_rows', 0))
    pcols[1].metric('Usable rows', parse_stats.get('usable_rows', 0))
    pcols[2].metric(t('wins'), parse_stats.get('wins', 0))
    pcols[3].metric(t('losses'), parse_stats.get('losses', 0))
    pcols[4].metric('Missing probability', parse_stats.get('missing_probability', 0))
    pcols[5].metric('Missing result', parse_stats.get('missing_result', 0))
    pcols[6].metric('Fallback rows', parse_stats.get('fallback_probability_rows', 0))
    if int(parse_stats.get('usable_rows', 0)) == 0:
        st.error('This file is not useful for training yet. It needs resolved win/loss results plus probability/odds or a confidence signal.')
    elif int(parse_stats.get('fallback_probability_rows', 0)) > 0:
        st.warning(f"{t('fallback_note')} Rows: {parse_stats.get('fallback_probability_rows', 0)}")
    else:
        st.success('This upload has usable resolved rows with direct probability/odds information.')
    if uploaded_rows:
        st.dataframe(pd.DataFrame(uploaded_rows).head(50), use_container_width=True, hide_index=True)
    else:
        st.error('This CSV has no usable resolved rows for training. It needs win/loss results plus either probabilities/odds or a confidence signal such as High confidence.')

settings = st.columns(4)
min_events = settings[0].number_input(t('min_events'), min_value=5, max_value=500, value=5, step=1)
max_rows = settings[1].number_input(t('max_rows'), min_value=10, max_value=10000, value=2500, step=100)
min_segment_records = settings[2].number_input(t('min_pattern_rows'), min_value=2, max_value=50, value=3, step=1)
max_segments = settings[3].number_input(t('max_patterns'), min_value=20, max_value=1000, value=160, step=20)
training_mode = st.radio(t('training_mode'), [t('replace'), t('merge')], index=0, horizontal=False)
save_to_github = st.toggle(t('save_github'), value=bool(get_secret('GITHUB_TOKEN', 'GH_TOKEN')))

if save_to_github and not get_secret('GITHUB_TOKEN', 'GH_TOKEN'):
    st.warning(t('missing_token'))

if st.button(t('button'), type='primary', use_container_width=True):
    if graded_upload is None:
        st.warning(t('upload_first'))
        st.stop()
    source_rows = [] if training_mode == t('replace') else existing_rows
    merged_rows, duplicates_removed = merge_dedupe_rows(source_rows, uploaded_rows)
    pruned_rows, prune_report = prune_rows(merged_rows, int(max_rows))
    if len(pruned_rows) < int(min_events):
        st.error(t('too_few').format(rows=len(pruned_rows), needed=int(min_events)))
        st.stop()
    graded_rows = rows_to_graded(pruned_rows)
    calibrator = fit_probability_calibrator(graded_rows, min_events=int(min_events), source=getattr(graded_upload, 'name', 'uploaded_graded_results.csv'))
    mode_name = 'replace' if training_mode == t('replace') else 'merge'
    calibrator.notes.append(f"Mode={mode_name}. Existing rows used={len(source_rows)}. Uploaded usable rows={len(uploaded_rows)}. Duplicates removed={duplicates_removed}. Trained on {len(pruned_rows)} rows.")
    if int(parse_stats.get('fallback_probability_rows', 0)) > 0:
        calibrator.notes.append(f"Used fallback confidence probability for {parse_stats.get('fallback_probability_rows', 0)} rows because probability/odds were missing.")
    segments = build_segments(pruned_rows, int(min_segment_records), int(max_segments))
    ara_csv = make_ara_memory_csv(segments)
    memory_bank = build_memory_bank(
        compact_rows=pruned_rows,
        calibrator=calibrator,
        segments=segments,
        parse_stats=parse_stats,
        prune_report=prune_report,
        mode=mode_name,
        existing_count=len(existing_rows),
        uploaded_count=len(uploaded_rows),
        duplicates_removed=duplicates_removed,
    )
    MEMORY_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_BANK_PATH.write_text(json.dumps(memory_bank, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    LEARNED_STATE_PATH.write_text(calibrator_json(calibrator), encoding='utf-8')
    ARA_MEMORY_PATH.write_text(ara_csv, encoding='utf-8')
    st.success(t('updated_local'))
    if save_to_github:
        try:
            today = datetime.now(timezone.utc).date().isoformat()
            github_put_text_file(path='learned_state.json', content=calibrator_json(calibrator), message=f'Update learned calibration {today}')
            github_put_text_file(path='data/learning_memory_bank.json', content=json.dumps(memory_bank, indent=2, sort_keys=True) + '\n', message=f'Update cumulative learning memory {today}')
            github_put_text_file(path='data/ara_learning_memory.csv', content=ara_csv, message=f'Update ARA memory patterns {today}')
            st.success(t('saved_github'))
        except Exception as exc:
            st.error(t('save_error').format(error=exc))
    st.subheader(t('training_summary'))
    st.json(summary_for_display(memory_bank['summary']))
    with st.expander(t('calibration_details'), expanded=False):
        st.json(calibrator.to_dict())
    st.subheader(t('top_patterns'))
    segments_frame = display_segments(segments[:40])
    st.dataframe(segments_frame, use_container_width=True, hide_index=True)
    download_csv = segments_frame.to_csv(index=False) if LANG == 'es' else ara_csv
    download_name = 'memoria_ara.csv' if LANG == 'es' else 'ara_learning_memory.csv'
    st.download_button(t('download_ara'), download_csv, file_name=download_name, mime='text/csv')
    st.info('Refresh the page after saving to see the top summary numbers change to the newly saved memory.')

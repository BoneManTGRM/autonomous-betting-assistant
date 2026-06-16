from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import agent_decision_summary, build_agent_decisions, lock_ready_candidates
from autonomous_betting_agent.four_tool_orchestrator import page_health, page_health_frame
from autonomous_betting_agent.live_api_context import LiveAPIContextBuilder
from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.multi_source_fusion import fuse_row
from autonomous_betting_agent.scanner_strength import score_scanner_frame, scanner_strength_summary

APP_VERSION = 'four-tool-pro-v16-pattern-memory-accuracy'
REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'
LEARNED_STATE_PATH = REPO_ROOT / 'learned_state.json'
DEFAULT_SPORT_KEYS = ['basketball_nba', 'baseball_mlb', 'soccer_epl', 'tennis_atp']

st.set_page_config(page_title='Pro Predictor', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='pro_predictor_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Pro Predictor',
        'caption': 'Main all-sports prediction engine. It scans live markets, applies learned memory, builds model probabilities, scores agent decisions, and forwards the highest-confidence rows to Odds Lock Pro.',
        'workflow': 'Clean path: Scanner Pro → Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory.',
        'version': 'App version', 'learned_events': 'Learned events', 'raw_accuracy': 'Raw accuracy', 'calibrated_accuracy': 'Calibrated accuracy', 'brier_after': 'Brier after',
        'api_sources': 'API sources', 'odds_key': 'Odds API key', 'sports_key': 'SportsDataIO key', 'weather_key': 'WeatherAPI key', 'enabled': 'Enabled', 'missing': 'Missing',
        'setup': 'Prediction setup', 'scan_scope': 'Scan scope', 'all_sports': 'All active sports', 'one_sport': 'One sport/league', 'team_player': 'One team/player', 'manual_sports': 'Manual sport keys only',
        'sport_search': 'Sport/feed search', 'team_filter': 'Team/player filter', 'manual_keys': 'Manual sport keys', 'regions': 'Bookmaker regions', 'markets': 'Markets', 'max_sports': 'Max sports', 'max_events': 'Max events per sport', 'latest_date': 'Latest event date',
        'min_books': 'Minimum books', 'min_model_prob': 'Minimum model probability', 'min_edge': 'Minimum edge', 'strong_edge': 'Strong edge threshold', 'min_strength': 'Minimum scanner strength', 'run': 'Run Pro Predictor',
        'api_error': 'Could not load sports list. Check API key/quota or use manual sport keys.', 'no_rows': 'No prediction rows passed the filters.', 'skipped': 'Skipped feeds / API errors', 'saved': 'Prediction rows saved. Highest-confidence rows are now the default handoff to Odds Lock Pro.',
        'ranked': 'Ranked prediction board', 'high_conf': 'Highest-confidence picks', 'lock_ready': 'Lock-ready candidates', 'all_rows': 'All rows', 'download': 'Download Pro Predictor CSV', 'download_high': 'Download highest-confidence CSV',
        'rows': 'Rows', 'playable': 'Playable', 'lock_ready_metric': 'Lock ready', 'avg_strength': 'Avg strength', 'premium': 'Premium scans', 'strong': 'Strong plays', 'small': 'Small plays', 'memory_source': 'Memory source', 'next': 'Next', 'handoff': 'Four-tool handoff health',
        'high_conf_setup': 'Highest-confidence output', 'use_high_conf': 'Send only highest-confidence rows to Odds Lock Pro', 'max_high_conf': 'Max high-confidence rows', 'min_high_prob': 'High-confidence min probability', 'min_high_edge': 'High-confidence min edge', 'min_high_strength': 'High-confidence min scanner strength', 'min_high_agent': 'High-confidence min agent score',
        'high_conf_count': 'High confidence', 'all_count': 'All passed', 'handoff_note': 'Odds Lock Pro will use this high-confidence session list first. The full scanned list remains downloadable in All rows.',
        'memory_patterns': 'Memory patterns', 'pattern_signal': 'Pattern signal', 'accuracy_mode': 'Accuracy mode',
    },
    'es': {
        'title': 'Predictor Pro',
        'caption': 'Motor principal de predicción. Escanea mercados, aplica memoria, crea probabilidades, califica decisiones y envía las filas de máxima confianza a Odds Lock Pro.',
        'workflow': 'Ruta limpia: Scanner Pro → Predictor Pro → Máxima Confianza → Odds Lock Pro → Dashboard Público → Memoria.',
        'version': 'Versión de la app', 'learned_events': 'Eventos aprendidos', 'raw_accuracy': 'Precisión bruta', 'calibrated_accuracy': 'Precisión calibrada', 'brier_after': 'Brier después',
        'api_sources': 'Fuentes API', 'odds_key': 'Clave de Odds API', 'sports_key': 'Clave de SportsDataIO', 'weather_key': 'Clave de WeatherAPI', 'enabled': 'Activada', 'missing': 'Falta',
        'setup': 'Configuración de predicción', 'scan_scope': 'Alcance del escaneo', 'all_sports': 'Todos los deportes activos', 'one_sport': 'Un deporte/liga', 'team_player': 'Un equipo/jugador', 'manual_sports': 'Solo claves manuales',
        'sport_search': 'Buscar deporte/feed', 'team_filter': 'Filtro de equipo/jugador', 'manual_keys': 'Claves manuales de deporte', 'regions': 'Regiones de casas de apuestas', 'markets': 'Mercados', 'max_sports': 'Máximo de deportes', 'max_events': 'Máximo de eventos por deporte', 'latest_date': 'Fecha máxima del evento',
        'min_books': 'Mínimo de casas', 'min_model_prob': 'Probabilidad mínima del modelo', 'min_edge': 'Ventaja mínima', 'strong_edge': 'Umbral de ventaja fuerte', 'min_strength': 'Fuerza mínima del escáner', 'run': 'Ejecutar Predictor Pro',
        'api_error': 'No se pudo cargar la lista de deportes. Revisa la clave/cuota API o usa claves manuales.', 'no_rows': 'Ninguna fila de predicción pasó los filtros.', 'skipped': 'Feeds omitidos / errores API', 'saved': 'Filas guardadas. Las filas de máxima confianza pasan por defecto a Odds Lock Pro.',
        'ranked': 'Tablero de predicciones clasificadas', 'high_conf': 'Picks de máxima confianza', 'lock_ready': 'Candidatos listos para bloquear', 'all_rows': 'Todas las filas', 'download': 'Descargar CSV de Predictor Pro', 'download_high': 'Descargar CSV de máxima confianza',
        'rows': 'Filas', 'playable': 'Jugables', 'lock_ready_metric': 'Listas para bloquear', 'avg_strength': 'Fuerza promedio', 'premium': 'Escaneos premium', 'strong': 'Jugadas fuertes', 'small': 'Jugadas pequeñas', 'memory_source': 'Fuente de memoria', 'next': 'Siguiente', 'handoff': 'Salud del traspaso entre herramientas',
        'high_conf_setup': 'Salida de máxima confianza', 'use_high_conf': 'Enviar solo filas de máxima confianza a Odds Lock Pro', 'max_high_conf': 'Máximo de filas de máxima confianza', 'min_high_prob': 'Probabilidad mínima máxima confianza', 'min_high_edge': 'Ventaja mínima máxima confianza', 'min_high_strength': 'Fuerza mínima máxima confianza', 'min_high_agent': 'Puntaje agente mínimo',
        'high_conf_count': 'Máxima confianza', 'all_count': 'Todas aprobadas', 'handoff_note': 'Odds Lock Pro usará primero esta lista de máxima confianza. La lista completa queda descargable en Todas las filas.',
        'memory_patterns': 'Patrones de memoria', 'pattern_signal': 'Señal de patrón', 'accuracy_mode': 'Modo precisión',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


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


def clean(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').split())


def similarity(left: Any, right: Any) -> float:
    left_clean, right_clean = clean(left), clean(right)
    if not left_clean or not right_clean:
        return 0.0
    if left_clean == right_clean or left_clean in right_clean or right_clean in left_clean:
        return 1.0
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def next_sunday(today: date | None = None) -> date:
    base = today or date.today()
    days = (6 - base.weekday()) % 7 or 7
    return base + timedelta(days=days)


def parse_event_date(value: Any) -> date | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date()


def parse_manual_keys(value: str) -> list[str]:
    keys: list[str] = []
    for item in value.replace('\n', ',').split(','):
        key = item.strip()
        if key and key not in keys:
            keys.append(key)
    return keys


def safe_float(value: Any) -> float | None:
    text = str(value or '').strip().replace('%', '').replace(',', '')
    if not text or text.lower() in {'none', 'null', 'nan', 'unknown', 'n/a'}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_probability_value(value: Any) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        parsed /= 100.0
    if 0.0 < parsed < 1.0:
        return parsed
    return None


def load_learned_state_summary() -> dict[str, Any]:
    try:
        if LEARNED_STATE_PATH.exists():
            payload = json.loads(LEARNED_STATE_PATH.read_text(encoding='utf-8'))
            return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    return {}


def probability_bucket(probability: float | None) -> str:
    if probability is None:
        return 'unknown'
    if probability < 0.40:
        return '0-40%'
    if probability < 0.50:
        return '40-50%'
    if probability < 0.60:
        return '50-60%'
    if probability < 0.70:
        return '60-70%'
    if probability < 0.80:
        return '70-80%'
    if probability < 0.90:
        return '80-90%'
    return '90-100%'


def books_bucket(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return 'unknown'
    if number <= 1:
        return '0-1'
    if number <= 3:
        return '2-3'
    if number <= 6:
        return '4-6'
    if number <= 10:
        return '7-10'
    return '11+'


def api_bucket(value: Any) -> str:
    number = safe_float(value)
    if number is None:
        return 'unknown'
    number = max(0.0, min(1.0, number))
    if number >= 0.999:
        return '100%'
    if number >= 0.66:
        return '66-99%'
    if number >= 0.33:
        return '33-65%'
    if number > 0:
        return '1-32%'
    return '0%'


def load_memory_patterns() -> tuple[list[dict[str, Any]], float, str, int]:
    try:
        if not REPO_MEMORY_PATH.exists():
            return [], 0.0, 'no_memory_signal', 0
        frame = pd.read_csv(REPO_MEMORY_PATH)
        if frame.empty:
            return [], 0.0, 'empty_ara_learning_memory', 0
        frame = frame.copy()
        frame['records_num'] = pd.to_numeric(frame.get('records', pd.Series(dtype=float)), errors='coerce').fillna(0).clip(lower=0, upper=100)
        frame['edge_num'] = pd.to_numeric(frame.get('smoothed_edge', pd.Series(dtype=float)), errors='coerce').fillna(0).clip(lower=-0.20, upper=0.20)
        frame['reliability_num'] = pd.to_numeric(frame.get('reliability', pd.Series(dtype=float)), errors='coerce').fillna(0.35).clip(lower=0.05, upper=1.0)
        usable = frame[frame['records_num'] >= 3].copy()
        if usable.empty:
            return [], 0.0, 'memory_loaded_no_reliable_patterns', int(len(frame))
        global_weight = usable['records_num'] * usable['reliability_num']
        global_signal = float((usable['edge_num'] * global_weight).sum() / global_weight.sum()) if global_weight.sum() else 0.0
        patterns = usable.to_dict('records')
        return patterns, round(max(-0.04, min(0.04, global_signal * 0.50)), 6), 'pattern_ara_learning_memory', int(len(frame))
    except Exception:
        return [], 0.0, 'memory_signal_error', 0


def memory_signal() -> tuple[float, str, int]:
    _patterns, signal, source, rows = load_memory_patterns()
    return signal, source, rows


def row_pattern_values(row: dict[str, Any]) -> set[tuple[str, str]]:
    sport = str(row.get('sport') or row.get('sport_key') or '').strip()
    market = str(row.get('market_type') or 'h2h').strip()
    probability = parse_probability_value(row.get('market_probability')) or parse_probability_value(row.get('model_probability'))
    bucket = probability_bucket(probability)
    values: set[tuple[str, str]] = {
        ('probability_bucket', bucket),
        ('market_type', market),
        ('books_bucket', books_bucket(row.get('books') or row.get('bookmaker_count'))),
        ('api_coverage_bucket', api_bucket(row.get('api_coverage_score'))),
    }
    if sport:
        values.add(('sport', sport))
        values.add(('sport_probability_bucket', f'{sport}|{bucket}'))
        values.add(('sport_market', f'{sport}|{market}'))
    confidence = str(row.get('confidence') or '').strip()
    if confidence:
        values.add(('confidence', confidence))
    return {(clean(left), clean(right)) for left, right in values if right and clean(right) != 'unknown'}


def pattern_memory_adjustment(row: dict[str, Any], patterns: list[dict[str, Any]]) -> tuple[float, str, int]:
    if not patterns:
        return 0.0, '', 0
    lookup = row_pattern_values(row)
    matches: list[tuple[float, float, str]] = []
    for pattern in patterns:
        key = (clean(pattern.get('area_type')), clean(pattern.get('group_value')))
        if key not in lookup:
            continue
        records = max(0.0, min(100.0, safe_float(pattern.get('records')) or 0.0))
        if records < 3:
            continue
        reliability = max(0.05, min(1.0, safe_float(pattern.get('reliability')) or 0.35))
        edge = max(-0.20, min(0.20, safe_float(pattern.get('smoothed_edge')) or 0.0))
        weight = (records ** 0.5) * reliability
        if weight <= 0:
            continue
        matches.append((edge, weight, str(pattern.get('area') or f"{pattern.get('area_type')}={pattern.get('group_value')}")))
    if not matches:
        return 0.0, '', 0
    weighted_edge = sum(edge * weight for edge, weight, _label in matches) / sum(weight for _edge, weight, _label in matches)
    adjustment = round(max(-0.045, min(0.045, weighted_edge * 0.65)), 6)
    strongest = sorted(matches, key=lambda item: abs(item[0] * item[1]), reverse=True)[:3]
    labels = '; '.join(label[:80] for _edge, _weight, label in strongest)
    return adjustment, labels, len(matches)


def api_coverage_fields(api_context: dict[str, Any], *, odds: bool, sports: bool, weather: bool) -> dict[str, Any]:
    configured, used = [], []
    if odds:
        configured.append('odds_api'); used.append('odds_api')
    if sports:
        configured.append('sportsdataio')
        if str(api_context.get('sportsdataio_source_used', '')).lower() == 'yes':
            used.append('sportsdataio')
    if weather:
        configured.append('weatherapi')
        if str(api_context.get('weather_source_used', '')).lower() == 'yes':
            used.append('weatherapi')
    score = 0.0 if not configured else round(len(used) / len(configured), 6)
    missing = [item for item in configured if item not in used]
    return {'configured_api_sources': ','.join(configured), 'api_sources_used': ','.join(used), 'api_sources_missing': ','.join(missing), 'api_coverage_score': score, 'api_coverage_percent': pct(score), 'all_configured_apis_used': bool(configured) and len(used) == len(configured)}


def sport_score(sport: Any, query: str) -> float:
    if not query.strip() or clean(query) == 'auto':
        return 0.5
    text = f"{getattr(sport, 'key', '')} {getattr(sport, 'title', '')} {getattr(sport, 'group', '')} {getattr(sport, 'description', '')}"
    return similarity(query, text)


def event_match_score(event: Any, query: str) -> float:
    if not query.strip():
        return 1.0
    text = f"{getattr(event, 'home_team', '')} {getattr(event, 'away_team', '')}"
    for outcome in getattr(event, 'outcomes', []) or []:
        text += f" {getattr(outcome, 'name', '')}"
    return similarity(query, text)


def numeric_series(frame: pd.DataFrame, names: list[str]) -> pd.Series:
    for name in names:
        if name in frame.columns:
            values = pd.to_numeric(frame[name], errors='coerce')
            if values.notna().any():
                if 'prob' in name.lower():
                    values = values.where(values <= 1.0, values / 100.0)
                return values
    return pd.Series(index=frame.index, dtype=float)


def high_confidence_shortlist(frame: pd.DataFrame, *, max_rows: int, min_probability: float, min_edge: float, min_strength: float, min_agent_score: float) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    probability = numeric_series(out, ['model_probability_clean', 'model_probability', 'final_probability_value', 'probability'])
    edge = numeric_series(out, ['model_market_edge', 'model_edge', 'computed_ev_decimal', 'estimated_ev_decimal'])
    strength = numeric_series(out, ['scanner_strength_score'])
    agent_score = numeric_series(out, ['agent_score'])
    pattern_signal = numeric_series(out, ['pattern_ara_memory_signal', 'ara_memory_signal'])
    if probability.notna().any():
        out['_hc_probability'] = probability
        out = out[out['_hc_probability'].fillna(0.0) >= float(min_probability)]
    if not out.empty and edge.notna().any():
        out['_hc_edge'] = edge.reindex(out.index)
        out = out[out['_hc_edge'].fillna(-999.0) >= float(min_edge)]
    if not out.empty and strength.notna().any():
        out['_hc_strength'] = strength.reindex(out.index)
        out = out[out['_hc_strength'].fillna(0.0) >= float(min_strength)]
    if not out.empty and agent_score.notna().any():
        out['_hc_agent_score'] = agent_score.reindex(out.index)
        out = out[out['_hc_agent_score'].fillna(0.0) >= float(min_agent_score)]
    if not out.empty and pattern_signal.notna().any() and edge.notna().any():
        memory = pattern_signal.reindex(out.index).fillna(0.0)
        current_edge = edge.reindex(out.index).fillna(-999.0)
        weak_learned_area = (memory < -0.015) & (current_edge < max(float(min_edge) + 0.025, 0.065))
        out = out[~weak_learned_area]
    if not out.empty:
        decision = out.get('agent_decision', pd.Series(index=out.index, dtype=str)).astype(str).str.lower()
        lock_ready = out.get('lock_ready', pd.Series(index=out.index, dtype=str)).astype(str).str.lower().isin(['true', '1', 'yes', 'y'])
        playable = decision.isin(['play_strong', 'play_small']) | lock_ready
        if playable.any():
            out = out[playable]
    sort_cols = [col for col in ['agent_score', 'scanner_strength_score', 'model_market_edge', 'pattern_ara_memory_signal', 'model_probability_clean', '_hc_probability'] if col in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, ascending=False, na_position='last')
    if int(max_rows) > 0:
        out = out.head(int(max_rows))
    return out.drop(columns=[col for col in ['_hc_probability', '_hc_edge', '_hc_strength', '_hc_agent_score'] if col in out.columns], errors='ignore').reset_index(drop=True)


def build_rows(
    events: list[Any],
    sport: Any,
    *,
    context_builder: LiveAPIContextBuilder,
    odds_key: str,
    sports_key: str,
    weather_key: str,
    team_filter: str,
    latest_event_date: date,
    global_memory_edge: float,
    memory_patterns: list[dict[str, Any]],
    min_books: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        event_day = parse_event_date(getattr(event, 'commence_time', ''))
        if event_day is None or event_day > latest_event_date:
            continue
        match = event_match_score(event, team_filter)
        if team_filter.strip() and match < 0.85:
            continue
        event_name = f"{getattr(event, 'away_team', '')} at {getattr(event, 'home_team', '')}".strip()
        sport_title = getattr(event, 'sport_title', getattr(sport, 'title', ''))
        sport_key = getattr(event, 'sport_key', getattr(sport, 'key', ''))
        for outcome in getattr(event, 'outcomes', []) or []:
            books = int(getattr(event, 'bookmaker_count', 0) or getattr(outcome, 'source_count', 0) or 0)
            if books < int(min_books):
                continue
            prediction = getattr(outcome, 'name', '')
            market_probability = float(getattr(outcome, 'normalized_probability', 0.0) or 0.0)
            best_price = getattr(outcome, 'best_price', None) or getattr(outcome, 'average_price', None)
            try:
                api_context = context_builder.context_for_event(event, pick_name=prediction)
            except Exception as exc:
                api_context = {'api_context_error': str(exc)[:180]}
            api_context.update(api_coverage_fields(api_context, odds=bool(odds_key), sports=bool(sports_key), weather=bool(weather_key)))
            preview = {
                'event': event_name,
                'sport': sport_title,
                'sport_key': sport_key,
                'market_type': 'h2h',
                'prediction': prediction,
                'market_probability': market_probability,
                'bookmaker_count': books,
                'books': books,
                **api_context,
            }
            pattern_adjustment, pattern_match, pattern_count = pattern_memory_adjustment(preview, memory_patterns)
            combined_memory_adjustment = round(max(-0.05, min(0.05, global_memory_edge + pattern_adjustment)), 6)
            fusion_input = {'market_probability': market_probability, 'learning_adjustment': combined_memory_adjustment}
            for key in ('stats_probability', 'injury_risk_score', 'weather_risk_score', 'weather_flag'):
                if api_context.get(key) not in (None, ''):
                    fusion_input[key] = api_context[key]
            fused = fuse_row(fusion_input)
            row = {
                'event': event_name, 'event_id': getattr(event, 'event_id', ''), 'sport': sport_title, 'sport_key': sport_key,
                'event_start_utc': getattr(event, 'commence_time', ''), 'event_date': str(event_day), 'home_team': getattr(event, 'home_team', ''), 'away_team': getattr(event, 'away_team', ''),
                'market_type': 'h2h', 'prediction': prediction, 'model_probability': round(float(fused.final_probability), 6), 'model_probability_clean': round(float(fused.final_probability), 6), 'market_probability': round(market_probability, 6),
                'decimal_price': best_price, 'best_price': best_price, 'average_price': getattr(outcome, 'average_price', None), 'worst_price': getattr(outcome, 'worst_price', None), 'price_range': getattr(outcome, 'price_range', None),
                'bookmaker': getattr(outcome, 'best_bookmaker', '') or '', 'bookmaker_count': books, 'books': books, 'market_overround': getattr(event, 'market_overround', None), 'odds_source': 'The Odds API',
                'ara_memory_signal': combined_memory_adjustment, 'global_ara_memory_signal': global_memory_edge, 'pattern_ara_memory_signal': pattern_adjustment, 'ara_memory_match_count': pattern_count, 'ara_memory_match': pattern_match,
                'final_probability': pct(float(fused.final_probability)), 'reliability_score': fused.reliability_score, 'confidence': fused.confidence, 'fusion_reason': fused.fusion_reason, 'fusion_warning': fused.fusion_warning,
                'match_score': f'{match:.0%}', 'prediction_timestamp': '', 'result_status': '',
            }
            row.update(api_context)
            rows.append(row)
    return rows


st.title(t('title'))
st.caption(t('caption'))
st.info(t('workflow'))
st.caption(f"{t('version')}: {APP_VERSION}")

learned = load_learned_state_summary()
memory_patterns, mem_edge, mem_source, mem_rows = load_memory_patterns()
learned_cols = st.columns(6)
learned_cols[0].metric(t('learned_events'), int(learned.get('events_trained', 0) or 0))
learned_cols[1].metric(t('raw_accuracy'), pct(float(learned.get('accuracy_before', 0) or 0)) if learned else 'N/A')
learned_cols[2].metric(t('calibrated_accuracy'), pct(float(learned.get('accuracy_after', 0) or 0)) if learned else 'N/A')
learned_cols[3].metric(t('brier_after'), f"{float(learned.get('brier_after', 0) or 0):.4f}" if learned else 'N/A')
learned_cols[4].metric(t('memory_patterns'), f'{mem_rows} rows')
learned_cols[5].metric(t('pattern_signal'), f'{mem_edge:+.4f}')
st.caption(f'{t("memory_source")}: {mem_source}; global_signal={mem_edge:.4f}; usable_patterns={len(memory_patterns)}')

st.subheader(t('api_sources'))
saved_odds = get_secret('ODDS_API_KEY', 'THE_ODDS_API_KEY')
saved_sports = get_secret('SPORTSDATAIO_API_KEY')
saved_weather = get_secret('WEATHERAPI_KEY', 'WEATHER_API_KEY')
api1, api2, api3 = st.columns(3)
odds_key = api1.text_input(t('odds_key'), type='password', placeholder='Loaded from secrets' if saved_odds else '').strip() or saved_odds
sports_key = api2.text_input(t('sports_key'), type='password', placeholder='Loaded from secrets' if saved_sports else '').strip() or saved_sports
weather_key = api3.text_input(t('weather_key'), type='password', placeholder='Loaded from secrets' if saved_weather else '').strip() or saved_weather
s1, s2, s3 = st.columns(3)
s1.metric('Odds API', t('enabled') if odds_key else t('missing'))
s2.metric('SportsDataIO', t('enabled') if sports_key else t('missing'))
s3.metric('WeatherAPI', t('enabled') if weather_key else t('missing'))

st.subheader(t('setup'))
left, right = st.columns(2)
with left:
    labels = [t('all_sports'), t('one_sport'), t('team_player'), t('manual_sports')]
    chosen = st.radio(t('scan_scope'), labels, horizontal=False)
    sport_query = st.text_input(t('sport_search'), value='auto')
    team_filter = st.text_input(t('team_filter'), value='')
    manual_keys = parse_manual_keys(st.text_input(t('manual_keys'), value='', help='basketball_nba, baseball_mlb, soccer_epl, tennis_atp'))
with right:
    regions = st.multiselect(t('regions'), ['us', 'us2', 'uk', 'eu', 'au'], default=['us', 'eu'])
    markets = st.multiselect(t('markets'), ['h2h', 'spreads', 'totals'], default=['h2h'])
    max_sports = st.number_input(t('max_sports'), min_value=1, max_value=120, value=25, step=1)
    max_events = st.number_input(t('max_events'), min_value=1, max_value=100, value=25, step=5)
    latest_event_date = st.date_input(t('latest_date'), value=next_sunday())

with st.expander('Filters' if LANG == 'en' else 'Filtros', expanded=True):
    st.caption(t('accuracy_mode') + ': stricter defaults favor hit-rate over volume.')
    f1, f2, f3, f4, f5 = st.columns(5)
    min_books = f1.number_input(t('min_books'), min_value=1, max_value=25, value=4, step=1)
    min_model_prob = f2.number_input(t('min_model_prob'), min_value=0.0, max_value=0.99, value=0.58, step=0.01)
    min_edge = f3.number_input(t('min_edge'), min_value=-0.25, max_value=0.50, value=0.04, step=0.005, format='%.3f')
    strong_edge = f4.number_input(t('strong_edge'), min_value=0.0, max_value=0.50, value=0.085, step=0.005, format='%.3f')
    min_strength = f5.number_input(t('min_strength'), min_value=0.0, max_value=100.0, value=50.0, step=1.0)

with st.expander(t('high_conf_setup'), expanded=True):
    h1, h2, h3, h4, h5 = st.columns(5)
    use_high_conf = h1.checkbox(t('use_high_conf'), value=True)
    max_high_conf = h2.number_input(t('max_high_conf'), min_value=1, max_value=100, value=25, step=5)
    min_high_prob = h3.number_input(t('min_high_prob'), min_value=0.0, max_value=0.99, value=0.62, step=0.01)
    min_high_edge = h4.number_input(t('min_high_edge'), min_value=-0.25, max_value=0.50, value=0.055, step=0.005, format='%.3f')
    min_high_strength = h5.number_input(t('min_high_strength'), min_value=0.0, max_value=100.0, value=65.0, step=1.0)
    min_high_agent = st.slider(t('min_high_agent'), min_value=0.0, max_value=100.0, value=65.0, step=1.0)

if st.button(t('run'), type='primary', use_container_width=True):
    if not odds_key:
        st.error('Odds API key is required.' if LANG == 'en' else 'La clave de Odds API es obligatoria.')
        st.stop()
    skipped: list[str] = []
    try:
        sports = list_sports(odds_key, include_all=False)
    except Exception as exc:
        st.warning(f"{t('api_error')} Error: {str(exc)[:220]}")
        sports = []
    scope = {labels[0]: 'all', labels[1]: 'one', labels[2]: 'team', labels[3]: 'manual'}[chosen]
    if scope == 'manual' or not sports:
        sport_keys = manual_keys or DEFAULT_SPORT_KEYS[:2]
        selected_sports = [type('Sport', (), {'key': key, 'title': key, 'group': '', 'description': ''})() for key in sport_keys]
    else:
        ranked_sports = sorted(sports, key=lambda sport: sport_score(sport, sport_query), reverse=True)
        selected_sports = ranked_sports[: int(max_sports)]
        if scope == 'one' and sport_query.strip() and clean(sport_query) != 'auto':
            selected_sports = [sport for sport in selected_sports if sport_score(sport, sport_query) >= 0.35]
        if scope == 'team' and team_filter.strip():
            selected_sports = selected_sports[: int(max_sports)]
    context_builder = LiveAPIContextBuilder(sportsdataio_key=sports_key, weatherapi_key=weather_key)
    rows: list[dict[str, Any]] = []
    progress = st.progress(0)
    for index, sport in enumerate(selected_sports):
        try:
            events = scan_market(odds_key, sport.key, regions=','.join(regions), max_events=int(max_events), markets=','.join(markets or ['h2h']))
        except Exception as exc:
            skipped.append(f'{getattr(sport, "title", sport.key)}: {str(exc)[:180]}')
            events = []
        rows.extend(build_rows(
            events,
            sport,
            context_builder=context_builder,
            odds_key=odds_key,
            sports_key=sports_key,
            weather_key=weather_key,
            team_filter=team_filter,
            latest_event_date=latest_event_date,
            global_memory_edge=mem_edge,
            memory_patterns=memory_patterns,
            min_books=int(min_books),
        ))
        progress.progress((index + 1) / max(1, len(selected_sports)))
    progress.empty()
    raw_frame = pd.DataFrame(rows)
    if raw_frame.empty:
        st.info(t('no_rows'))
        if skipped:
            with st.expander(t('skipped')):
                for item in skipped[:80]:
                    st.write(f'- {item}')
        st.stop()
    scored = score_scanner_frame(raw_frame)
    decisions = build_agent_decisions(scored, min_edge=float(min_edge), strong_edge=float(strong_edge))
    if 'model_probability_clean' in decisions.columns:
        decisions = decisions[pd.to_numeric(decisions['model_probability_clean'], errors='coerce').fillna(0) >= float(min_model_prob)]
    if 'scanner_strength_score' in decisions.columns:
        decisions = decisions[pd.to_numeric(decisions['scanner_strength_score'], errors='coerce').fillna(0) >= float(min_strength)]
    if decisions.empty:
        st.info(t('no_rows'))
        st.stop()
    sort_cols = [col for col in ['agent_score', 'scanner_strength_score', 'model_market_edge', 'pattern_ara_memory_signal', 'model_probability_clean'] if col in decisions.columns]
    if sort_cols:
        decisions = decisions.sort_values(sort_cols, ascending=False).reset_index(drop=True)
    high_conf = high_confidence_shortlist(decisions, max_rows=int(max_high_conf), min_probability=float(min_high_prob), min_edge=float(min_high_edge), min_strength=float(min_high_strength), min_agent_score=float(min_high_agent))
    handoff = high_conf if use_high_conf and not high_conf.empty else decisions
    summary = agent_decision_summary(decisions, min_edge=float(min_edge), strong_edge=float(strong_edge))
    strength = scanner_strength_summary(decisions)
    health = page_health(handoff, page='pro_predictor')
    lock_ready = lock_ready_candidates(decisions, min_edge=float(min_edge), strong_edge=float(strong_edge))
    playable = int(summary['play_strong'] + summary['play_small'])
    st.session_state['pro_predictor_all_rows'] = decisions.to_dict('records')
    st.session_state['pro_predictor_high_confidence_rows'] = high_conf.to_dict('records')
    st.session_state['pro_predictor_latest_rows'] = handoff.to_dict('records')
    st.session_state['ara_latest_predictions'] = handoff.to_dict('records')
    st.session_state['ara_latest_predictions_source'] = 'Pro Predictor high-confidence' if use_high_conf else 'Pro Predictor all rows'
    st.session_state['ara_latest_predictions_saved_at'] = pd.Timestamp.utcnow().isoformat()
    st.success(t('saved'))
    st.info(t('handoff_note'))
    metrics = st.columns(9)
    metrics[0].metric(t('all_count'), len(decisions))
    metrics[1].metric(t('high_conf_count'), len(high_conf))
    metrics[2].metric(t('playable'), playable)
    metrics[3].metric(t('strong'), summary['play_strong'])
    metrics[4].metric(t('small'), summary['play_small'])
    metrics[5].metric(t('lock_ready_metric'), health['lock_ready_rows'])
    metrics[6].metric(t('avg_strength'), 'N/A' if strength['avg_score'] is None else strength['avg_score'])
    metrics[7].metric(t('premium'), strength['premium_scan'])
    metrics[8].metric(t('next'), health['next_action'])
    st.subheader(t('handoff'))
    st.dataframe(page_health_frame(handoff, page='pro_predictor'), use_container_width=True, hide_index=True)
    tabs = st.tabs([t('high_conf'), t('ranked'), t('lock_ready'), t('all_rows'), t('skipped')])
    display_cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'model_probability_clean', 'market_implied_probability', 'model_market_edge', 'pattern_ara_memory_signal', 'ara_memory_match_count', 'decimal_price', 'bookmaker', 'agent_decision', 'agent_score', 'scanner_strength_score', 'scanner_strength_tier', 'lock_ready', 'decision_reasons'] if col in decisions.columns]
    with tabs[0]:
        if high_conf.empty:
            st.info(t('no_rows'))
        else:
            st.dataframe(high_conf[display_cols] if display_cols else high_conf, use_container_width=True, hide_index=True)
            st.download_button(t('download_high'), high_conf.to_csv(index=False), file_name='pro_predictor_high_confidence.csv', mime='text/csv')
    with tabs[1]:
        st.dataframe(decisions[display_cols].head(100) if display_cols else decisions.head(100), use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(lock_ready, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(decisions, use_container_width=True, hide_index=True)
        st.download_button(t('download'), decisions.to_csv(index=False), file_name='pro_predictor_max_predictions.csv', mime='text/csv')
    with tabs[4]:
        if skipped:
            for item in skipped[:100]:
                st.write(f'- {item}')
        else:
            st.caption('No skipped feeds.' if LANG == 'en' else 'No hubo feeds omitidos.')

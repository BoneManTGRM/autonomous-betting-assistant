from __future__ import annotations

import base64
import html
import os
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.adaptive_learning import apply_adaptive_learning
from autonomous_betting_agent.four_tool_orchestrator import page_health, page_health_frame
from autonomous_betting_agent.live_api_context import LiveAPIContextBuilder
from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.multi_source_fusion import fuse_row
from autonomous_betting_agent.pick_hold_store import save_held_rows
from autonomous_betting_agent.scanner_strength import score_scanner_frame, scanner_strength_summary

APP_VERSION = 'pro-predictor-v21-adaptive-learning-ranker'
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPORT_KEYS = ['basketball_nba', 'baseball_mlb', 'soccer_epl']

st.set_page_config(page_title='Pro Predictor', layout='wide')
LANG = render_app_sidebar('pro_predictor', language_key='pro_predictor_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Pro Predictor',
        'caption': 'Scans markets, scores candidates, applies learned pattern ranking, and sends the ranked large-list output to Odds Lock Pro.',
        'workflow': 'Clean path: Pro Predictor → Adaptive Learning Ranker → Odds Lock Pro → Public Proof Dashboard → Learning Memory.',
        'api_sources': 'API sources', 'odds_key': 'Odds API key', 'sports_key': 'SportsDataIO key', 'weather_key': 'WeatherAPI key', 'enabled': 'Enabled', 'missing': 'Missing',
        'setup': 'Prediction setup', 'scan_scope': 'Scan scope', 'all_sports': 'All active sports', 'one_sport': 'One sport/league', 'team_player': 'One team/player', 'manual_sports': 'Manual sport keys only',
        'sport_search': 'Sport/feed search', 'team_filter': 'Team/player filter', 'manual_keys': 'Manual sport keys', 'regions': 'Bookmaker regions', 'markets': 'Markets', 'max_sports': 'Max sports', 'max_events': 'Max events per sport', 'latest_date': 'Latest event date',
        'filters': 'Filters', 'min_books': 'Minimum books', 'min_prob': 'Minimum model probability', 'min_edge': 'Minimum edge', 'strong_edge': 'Strong edge threshold', 'min_signal': 'Minimum signal strength',
        'large_setup': 'Large-list volume output', 'send_large': 'Send large-list volume rows to Odds Lock Pro', 'max_rows': 'Max large-list rows', 'min_agent': 'Large-list min learned score',
        'run': 'Run Pro Predictor', 'saved': 'Large-list rows saved to session, local memory, and Odds Lock Pro handoff store.', 'no_rows': 'No prediction rows passed the filters.', 'api_error': 'Could not load sports list. Check API key/quota or use manual sport keys.',
        'all_count': 'All passed', 'large_count': 'Large list', 'lock_ready': 'Lock ready', 'avg_signal': 'Avg signal', 'premium': 'Premium signals', 'next': 'Next', 'handoff': 'Handoff health',
        'large_tab': 'Large-list volume', 'all_tab': 'All rows', 'lock_tab': 'Lock-ready subset', 'skipped': 'Skipped feeds / API errors', 'download_large': 'Download large-list CSV', 'download_all': 'Download all rows CSV', 'no_skipped': 'No skipped feeds.',
        'profile_note': 'Adaptive Learning Ranker uses Learning Memory patterns to boost historically profitable patterns and penalize weak patterns before choosing the top 300.',
    },
    'es': {
        'title': 'Predictor Pro',
        'caption': 'Escanea mercados, califica candidatos, aplica ranking aprendido y envía la lista grande a Odds Lock Pro.',
        'workflow': 'Ruta limpia: Predictor Pro → Ranking Aprendido → Odds Lock Pro → Dashboard Público → Memoria.',
        'api_sources': 'Fuentes API', 'odds_key': 'Clave de Odds API', 'sports_key': 'Clave de SportsDataIO', 'weather_key': 'Clave de WeatherAPI', 'enabled': 'Activada', 'missing': 'Falta',
        'setup': 'Configuración de predicción', 'scan_scope': 'Alcance', 'all_sports': 'Todos los deportes activos', 'one_sport': 'Un deporte/liga', 'team_player': 'Un equipo/jugador', 'manual_sports': 'Solo claves manuales',
        'sport_search': 'Buscar deporte/feed', 'team_filter': 'Filtro de equipo/jugador', 'manual_keys': 'Claves manuales de deporte', 'regions': 'Regiones de casas', 'markets': 'Mercados', 'max_sports': 'Máximo de deportes', 'max_events': 'Máximo de eventos por deporte', 'latest_date': 'Fecha máxima del evento',
        'filters': 'Filtros', 'min_books': 'Mínimo de casas', 'min_prob': 'Probabilidad mínima del modelo', 'min_edge': 'Ventaja mínima', 'strong_edge': 'Umbral de ventaja fuerte', 'min_signal': 'Fuerza mínima de señal',
        'large_setup': 'Salida de lista grande', 'send_large': 'Enviar lista grande a Odds Lock Pro', 'max_rows': 'Máximo de filas de lista grande', 'min_agent': 'Puntaje aprendido mínimo',
        'run': 'Ejecutar Predictor Pro', 'saved': 'Lista grande guardada en sesión, memoria local y traspaso a Odds Lock Pro.', 'no_rows': 'Ninguna fila pasó los filtros.', 'api_error': 'No se pudo cargar la lista de deportes. Revisa la clave/cuota API o usa claves manuales.',
        'all_count': 'Todas aprobadas', 'large_count': 'Lista grande', 'lock_ready': 'Listas para bloquear', 'avg_signal': 'Señal promedio', 'premium': 'Señales premium', 'next': 'Siguiente', 'handoff': 'Salud del traspaso',
        'large_tab': 'Lista grande', 'all_tab': 'Todas las filas', 'lock_tab': 'Subconjunto listo', 'skipped': 'Feeds omitidos / errores API', 'download_large': 'Descargar CSV lista grande', 'download_all': 'Descargar CSV total', 'no_skipped': 'No hubo feeds omitidos.',
        'profile_note': 'El ranking aprendido usa patrones de Memoria para subir patrones rentables y penalizar patrones débiles antes de escoger el top 300.',
    },
}

DEFAULTS = {'min_books': 1, 'min_prob': 0.58, 'min_edge': -0.03, 'strong_edge': 0.04, 'min_signal': 38.0, 'max_rows': 300, 'min_agent': 35.0}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


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


def csv_link(label: str, frame: pd.DataFrame, filename: str) -> None:
    data = base64.b64encode(frame.to_csv(index=False).encode('utf-8')).decode('ascii')
    st.markdown(f'<a href="data:text/csv;base64,{data}" download="{html.escape(filename)}" style="display:block;text-align:center;background:#ef5350;color:white;padding:.75rem 1rem;border-radius:.45rem;text-decoration:none;font-weight:700;">{html.escape(label)}</a>', unsafe_allow_html=True)


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


def future_lock_ready(value: Any) -> bool:
    text = str(value or '').strip()
    if not text:
        return False
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        start = datetime.fromisoformat(text)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < start.astimezone(timezone.utc)
    except Exception:
        return False


def parse_manual_keys(value: str) -> list[str]:
    keys: list[str] = []
    for item in value.replace('\n', ',').split(','):
        key = item.strip()
        if key and key not in keys:
            keys.append(key)
    return keys


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


def pct(value: float | None) -> str:
    return 'N/A' if value is None else f'{value * 100:.1f}%'


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
    return {'configured_api_sources': ','.join(configured), 'api_sources_used': ','.join(used), 'api_coverage_score': score, 'api_coverage_percent': pct(score)}


def build_rows(events: list[Any], sport: Any, *, context_builder: LiveAPIContextBuilder, odds_key: str, sports_key: str, weather_key: str, team_filter: str, latest_event_date: date, min_books: int) -> list[dict[str, Any]]:
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
            market_type = getattr(outcome, 'market', 'h2h') or 'h2h'
            line_point = getattr(outcome, 'point', None)
            market_probability = float(getattr(outcome, 'normalized_probability', 0.0) or 0.0)
            best_price = getattr(outcome, 'best_price', None) or getattr(outcome, 'average_price', None)
            try:
                api_context = context_builder.context_for_event(event, pick_name=prediction)
            except Exception as exc:
                api_context = {'api_context_error': str(exc)[:180]}
            api_context.update(api_coverage_fields(api_context, odds=bool(odds_key), sports=bool(sports_key), weather=bool(weather_key)))
            fused = fuse_row({'market_probability': market_probability, 'learning_adjustment': 0.0})
            model_probability = round(float(fused.final_probability), 6)
            implied = None if not best_price or float(best_price) <= 1 else round(1 / float(best_price), 6)
            edge = None if implied is None else round(model_probability - implied, 6)
            rows.append({
                'event': event_name, 'event_id': getattr(event, 'event_id', ''), 'sport': sport_title, 'sport_key': sport_key,
                'event_start_utc': getattr(event, 'commence_time', ''), 'event_date': str(event_day), 'home_team': getattr(event, 'home_team', ''), 'away_team': getattr(event, 'away_team', ''),
                'market_type': market_type, 'line_point': line_point, 'prediction': prediction, 'model_probability': model_probability, 'model_probability_clean': model_probability, 'market_probability': round(market_probability, 6),
                'market_implied_probability': implied, 'model_market_edge': edge, 'decimal_price': best_price, 'odds_at_pick': best_price, 'best_price': best_price, 'average_price': getattr(outcome, 'average_price', None), 'worst_price': getattr(outcome, 'worst_price', None),
                'bookmaker': getattr(outcome, 'best_bookmaker', '') or '', 'bookmaker_count': books, 'books': books, 'market_overround': getattr(event, 'market_overround', None), 'odds_source': 'The Odds API',
                'final_probability': pct(model_probability), 'reliability_score': fused.reliability_score, 'confidence': fused.confidence, 'fusion_reason': fused.fusion_reason, 'fusion_warning': fused.fusion_warning,
                'match_score': f'{match:.0%}', 'prediction_timestamp': '', 'result_status': '', **api_context,
            })
    return rows


def add_large_list_scores(frame: pd.DataFrame, *, strong_edge: float) -> pd.DataFrame:
    out = frame.copy()
    prob = pd.to_numeric(out.get('model_probability_clean'), errors='coerce').fillna(0.0)
    edge = pd.to_numeric(out.get('model_market_edge'), errors='coerce').fillna(0.0)
    signal = pd.to_numeric(out.get('scanner_strength_score'), errors='coerce').fillna(0.0)
    coverage = pd.to_numeric(out.get('api_coverage_score'), errors='coerce').fillna(0.0)
    out['agent_score'] = (prob * 55.0 + edge.clip(-0.10, 0.15) * 180.0 + signal * 0.20 + coverage * 8.0).clip(0, 100).round(3)
    out['agent_decision'] = 'play_small'
    out.loc[(edge >= float(strong_edge)) & (prob >= 0.66), 'agent_decision'] = 'play_strong'
    out['decision_rank'] = out['agent_decision'].map({'play_strong': 1, 'play_small': 2}).fillna(3)
    out['lock_ready'] = out['event_start_utc'].apply(future_lock_ready)
    out['decision_reasons'] = ''
    out['decision_signals'] = 'large_list_volume_candidate'
    out['recommended_stake_units'] = 0.10
    out = apply_adaptive_learning(out)
    out['agent_score'] = pd.to_numeric(out.get('learned_agent_score'), errors='coerce').fillna(out['agent_score']).round(3)
    out['decision_signals'] = out['decision_signals'].astype(str) + '; adaptive_learning_ranker'
    return out


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rename(columns={'scanner_strength_score': 'signal_strength_score', 'scanner_strength_tier': 'signal_strength_tier'})


def persist_handoff(*, decisions: pd.DataFrame, large: pd.DataFrame, handoff: pd.DataFrame) -> None:
    workspace_id = str(st.session_state.get('aba_test_window_id', 'test_01') or 'test_01')
    save_held_rows('pro_predictor_latest_rows', handoff, workspace_id)
    save_held_rows('pro_predictor_high_confidence_rows', large, workspace_id)
    save_held_rows('ara_latest_predictions', handoff, workspace_id)
    save_held_rows('pro_predictor_latest_rows', handoff, 'test_01')
    save_held_rows('pro_predictor_high_confidence_rows', large, 'test_01')
    save_held_rows('ara_latest_predictions', handoff, 'test_01')


st.title(t('title'))
st.caption(t('caption'))
st.info(t('workflow'))
st.caption(f"App version: {APP_VERSION}")

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
st.caption(t('profile_note'))
left, right = st.columns(2)
with left:
    labels = [t('all_sports'), t('one_sport'), t('team_player'), t('manual_sports')]
    chosen = st.radio(t('scan_scope'), labels, horizontal=False)
    sport_query = st.text_input(t('sport_search'), value='auto')
    team_filter = st.text_input(t('team_filter'), value='')
    manual_keys = parse_manual_keys(st.text_input(t('manual_keys'), value='', help='basketball_nba, baseball_mlb, soccer_epl'))
with right:
    regions = st.multiselect(t('regions'), ['us', 'us2', 'uk', 'eu', 'au'], default=['us', 'us2', 'eu', 'uk'])
    markets = st.multiselect(t('markets'), ['h2h', 'spreads', 'totals'], default=['h2h', 'spreads', 'totals'])
    max_sports = st.number_input(t('max_sports'), min_value=1, max_value=250, value=50, step=1)
    max_events = st.number_input(t('max_events'), min_value=1, max_value=500, value=500, step=25)
    latest_event_date = st.date_input(t('latest_date'), value=next_sunday())

with st.expander(t('filters'), expanded=True):
    f1, f2, f3, f4, f5 = st.columns(5)
    min_books = f1.number_input(t('min_books'), min_value=1, max_value=25, value=DEFAULTS['min_books'], step=1)
    min_prob = f2.number_input(t('min_prob'), min_value=0.0, max_value=0.99, value=DEFAULTS['min_prob'], step=0.01)
    min_edge = f3.number_input(t('min_edge'), min_value=-0.25, max_value=0.50, value=DEFAULTS['min_edge'], step=0.005, format='%.3f')
    strong_edge = f4.number_input(t('strong_edge'), min_value=0.0, max_value=0.50, value=DEFAULTS['strong_edge'], step=0.005, format='%.3f')
    min_signal = f5.number_input(t('min_signal'), min_value=0.0, max_value=100.0, value=DEFAULTS['min_signal'], step=1.0)

with st.expander(t('large_setup'), expanded=True):
    h1, h2, h3 = st.columns(3)
    send_large = h1.checkbox(t('send_large'), value=True)
    max_rows = h2.number_input(t('max_rows'), min_value=1, max_value=500, value=DEFAULTS['max_rows'], step=25)
    min_agent = h3.number_input(t('min_agent'), min_value=0.0, max_value=100.0, value=DEFAULTS['min_agent'], step=1.0)

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
        selected_sports = sorted(sports, key=lambda sport: sport_score(sport, sport_query), reverse=True)[: int(max_sports)]
        if scope == 'one' and sport_query.strip() and clean(sport_query) != 'auto':
            selected_sports = [sport for sport in selected_sports if sport_score(sport, sport_query) >= 0.35]
    context_builder = LiveAPIContextBuilder(sportsdataio_key=sports_key, weatherapi_key=weather_key)
    rows: list[dict[str, Any]] = []
    progress = st.progress(0)
    for index, sport in enumerate(selected_sports):
        try:
            events = scan_market(odds_key, sport.key, regions=','.join(regions), max_events=int(max_events), markets=','.join(markets or ['h2h']))
        except Exception as exc:
            skipped.append(f'{getattr(sport, "title", sport.key)}: {str(exc)[:180]}')
            events = []
        rows.extend(build_rows(events, sport, context_builder=context_builder, odds_key=odds_key, sports_key=sports_key, weather_key=weather_key, team_filter=team_filter, latest_event_date=latest_event_date, min_books=int(min_books)))
        progress.progress((index + 1) / max(1, len(selected_sports)))
    progress.empty()
    raw = pd.DataFrame(rows)
    if raw.empty:
        st.info(t('no_rows'))
        st.stop()
    scored = score_scanner_frame(raw)
    decisions = add_large_list_scores(scored, strong_edge=float(strong_edge))
    decisions = decisions[pd.to_numeric(decisions['model_probability_clean'], errors='coerce').fillna(0) >= float(min_prob)]
    decisions = decisions[pd.to_numeric(decisions.get('model_market_edge'), errors='coerce').fillna(-999) >= float(min_edge)]
    decisions = decisions[pd.to_numeric(decisions.get('scanner_strength_score'), errors='coerce').fillna(0) >= float(min_signal)]
    decisions = decisions[pd.to_numeric(decisions.get('agent_score'), errors='coerce').fillna(0) >= float(min_agent)]
    if decisions.empty:
        st.info(t('no_rows'))
        st.stop()
    sort_cols = [col for col in ['learned_agent_score', 'agent_score', 'learning_adjustment_score', 'scanner_strength_score', 'model_probability_clean', 'model_market_edge'] if col in decisions.columns]
    decisions = decisions.sort_values(sort_cols, ascending=False, na_position='last').reset_index(drop=True)
    large = decisions.head(int(max_rows)).reset_index(drop=True)
    lock_ready = large[large['lock_ready'].astype(bool)].copy() if 'lock_ready' in large.columns else pd.DataFrame()
    handoff = large if send_large else decisions
    st.session_state['pro_predictor_all_rows'] = decisions.to_dict('records')
    st.session_state['pro_predictor_high_confidence_rows'] = large.to_dict('records')
    st.session_state['pro_predictor_latest_rows'] = handoff.to_dict('records')
    st.session_state['ara_latest_predictions'] = handoff.to_dict('records')
    st.session_state['ara_latest_predictions_source'] = 'Pro Predictor adaptive large-list volume' if send_large else 'Pro Predictor adaptive all rows'
    st.session_state['ara_latest_predictions_saved_at'] = pd.Timestamp.utcnow().isoformat()
    persist_handoff(decisions=decisions, large=large, handoff=handoff)
    st.success(t('saved'))
    strength = scanner_strength_summary(decisions)
    health = page_health(handoff, page='pro_predictor')
    metrics = st.columns(6)
    metrics[0].metric(t('all_count'), len(decisions))
    metrics[1].metric(t('large_count'), len(large))
    metrics[2].metric(t('lock_ready'), len(lock_ready))
    metrics[3].metric(t('avg_signal'), 'N/A' if strength['avg_score'] is None else strength['avg_score'])
    metrics[4].metric(t('premium'), strength['premium_scan'])
    metrics[5].metric(t('next'), health['next_action'])
    st.subheader(t('handoff'))
    st.dataframe(display_frame(page_health_frame(handoff, page='pro_predictor')), use_container_width=True, hide_index=True)
    tabs = st.tabs([t('large_tab'), t('all_tab'), t('lock_tab'), t('skipped')])
    display_cols = [col for col in ['event', 'sport', 'market_type', 'line_point', 'prediction', 'model_probability_clean', 'learned_model_probability', 'market_implied_probability', 'model_market_edge', 'decimal_price', 'odds_at_pick', 'bookmaker', 'agent_decision', 'agent_score', 'learning_adjustment_score', 'learning_pattern_count', 'scanner_strength_score', 'scanner_strength_tier', 'lock_ready', 'learning_notes', 'decision_signals'] if col in decisions.columns]
    with tabs[0]:
        st.dataframe(display_frame(large[display_cols] if display_cols else large), use_container_width=True, hide_index=True)
        csv_link(t('download_large'), display_frame(large), 'pro_predictor_large_list_volume.csv')
    with tabs[1]:
        st.dataframe(display_frame(decisions[display_cols] if display_cols else decisions), use_container_width=True, hide_index=True)
        csv_link(t('download_all'), display_frame(decisions), 'pro_predictor_all_predictions.csv')
    with tabs[2]:
        st.dataframe(display_frame(lock_ready), use_container_width=True, hide_index=True)
    with tabs[3]:
        if skipped:
            for item in skipped[:100]:
                st.write(f'- {item}')
        else:
            st.caption(t('no_skipped'))

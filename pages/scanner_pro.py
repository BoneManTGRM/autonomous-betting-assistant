from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scanner_strength import score_scanner_frame, scanner_strength_summary

st.set_page_config(page_title='Scanner Pro', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='scanner_pro_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Scanner Pro',
        'caption': 'One consolidated scanner for supported sports, leagues, markets, books, and live odds feeds.',
        'info': 'Use Scanner Pro for live market discovery. Use Pro Predictor for final scoring, What Are the Odds for market review, and Learning Memory for training.',
        'api_key': 'Odds API key',
        'missing_key': 'Missing Odds API key. Add THE_ODDS_API_KEY or ODDS_API_KEY in Streamlit secrets.',
        'api_error': 'Could not load the sports list. Check the API key, quota, or API access. You can still scan with manual sport keys below.',
        'manual_keys': 'Manual sport keys',
        'manual_help': 'Comma-separated examples: basketball_nba, baseball_mlb, soccer_epl, tennis_atp',
        'scan_scope': 'Scan scope',
        'all_sports': 'All active sports',
        'one_sport': 'One sport/league',
        'manual_sports': 'Manual sport keys only',
        'sport_search': 'Sport search',
        'max_sports': 'Max sports to scan',
        'max_events': 'Max events per sport',
        'regions': 'Bookmaker regions',
        'markets': 'Markets',
        'min_books': 'Minimum books',
        'run': 'Run Scanner Pro',
        'rows': 'Rows',
        'sports': 'Sports',
        'events': 'Events',
        'books': 'Avg books',
        'best_price_rows': 'Rows with best price',
        'avg_strength': 'Avg strength',
        'premium': 'Premium',
        'usable': 'Usable',
        'moneyline': 'Moneyline outcomes',
        'spreads': 'Spreads',
        'totals': 'Totals',
        'top_scans': 'Top scanner-ranked markets',
        'download': 'Download Scanner Pro CSV',
        'no_rows': 'No rows returned. Try fewer filters, another region, or a valid manual sport key.',
        'stored': 'Scanner rows saved in session for What Are the Odds and Learning Memory review.',
        'skipped': 'Skipped sports / API errors',
    },
    'es': {
        'title': 'Scanner Pro',
        'caption': 'Escáner único para deportes, ligas, mercados, casas de apuestas y cuotas en vivo compatibles.',
        'info': 'Usa Scanner Pro para descubrir mercados en vivo. Usa Pro Predictor para calificación final, What Are the Odds para revisar mercado y Memoria de Aprendizaje para entrenar.',
        'api_key': 'Clave de Odds API',
        'missing_key': 'Falta la clave de Odds API. Agrega THE_ODDS_API_KEY u ODDS_API_KEY en secretos de Streamlit.',
        'api_error': 'No se pudo cargar la lista de deportes. Revisa la clave, cuota o acceso de API. Todavía puedes escanear con claves manuales abajo.',
        'manual_keys': 'Claves manuales de deporte',
        'manual_help': 'Ejemplos separados por comas: basketball_nba, baseball_mlb, soccer_epl, tennis_atp',
        'scan_scope': 'Alcance del escaneo',
        'all_sports': 'Todos los deportes activos',
        'one_sport': 'Un deporte/liga',
        'manual_sports': 'Solo claves manuales',
        'sport_search': 'Buscar deporte',
        'max_sports': 'Máximo de deportes a escanear',
        'max_events': 'Máximo de eventos por deporte',
        'regions': 'Regiones de casas de apuestas',
        'markets': 'Mercados',
        'min_books': 'Mínimo de casas',
        'run': 'Ejecutar Scanner Pro',
        'rows': 'Filas',
        'sports': 'Deportes',
        'events': 'Eventos',
        'books': 'Promedio de casas',
        'best_price_rows': 'Filas con mejor cuota',
        'avg_strength': 'Fuerza promedio',
        'premium': 'Premium',
        'usable': 'Utilizables',
        'moneyline': 'Resultados moneyline',
        'spreads': 'Spreads',
        'totals': 'Totales',
        'top_scans': 'Mercados mejor calificados por el escáner',
        'download': 'Descargar CSV de Scanner Pro',
        'no_rows': 'No se encontraron filas. Prueba menos filtros, otra región o una clave manual válida.',
        'stored': 'Las filas se guardaron en sesión para What Are the Odds y Memoria de Aprendizaje.',
        'skipped': 'Deportes omitidos / errores API',
    },
}

DEFAULT_SPORT_KEYS = ['basketball_nba', 'baseball_mlb', 'soccer_epl', 'tennis_atp']


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


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


def parse_manual_keys(value: str) -> list[str]:
    keys: list[str] = []
    for item in value.replace('\n', ',').split(','):
        key = item.strip()
        if key and key not in keys:
            keys.append(key)
    return keys


def h2h_rows(summary: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    event = f'{summary.away_team} at {summary.home_team}' if summary.away_team and summary.home_team else summary.event_id
    for outcome in summary.outcomes:
        rows.append({
            'scanner_source': 'scanner_pro_live_odds',
            'event_id': summary.event_id,
            'event': event,
            'sport': summary.sport_title,
            'sport_key': summary.sport_key,
            'event_start_utc': summary.commence_time,
            'home_team': summary.home_team,
            'away_team': summary.away_team,
            'market_type': 'h2h',
            'prediction': outcome.name,
            'model_probability': round(float(outcome.normalized_probability), 6),
            'market_probability': round(float(outcome.normalized_probability), 6),
            'decimal_price': outcome.best_price or outcome.average_price,
            'average_price': outcome.average_price,
            'best_price': outcome.best_price,
            'worst_price': outcome.worst_price,
            'price_range': outcome.price_range,
            'bookmaker': outcome.best_bookmaker,
            'bookmaker_count': outcome.source_count,
            'books': outcome.source_count,
            'market_overround': summary.market_overround,
            'odds_source': 'The Odds API',
            'decision': 'scanner_only',
        })
    return rows


def line_rows(summary: Any, attr: str, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    event = f'{summary.away_team} at {summary.home_team}' if summary.away_team and summary.home_team else summary.event_id
    for line in getattr(summary, attr) or []:
        rows.append({
            'scanner_source': 'scanner_pro_live_odds',
            'event_id': summary.event_id,
            'event': event,
            'sport': summary.sport_title,
            'sport_key': summary.sport_key,
            'event_start_utc': summary.commence_time,
            'home_team': summary.home_team,
            'away_team': summary.away_team,
            'market_type': label,
            'prediction': line.name,
            'point': line.point,
            'decimal_price': line.best_price or line.average_price,
            'average_price': line.average_price,
            'best_price': line.best_price,
            'worst_price': line.worst_price,
            'price_range': line.price_range,
            'bookmaker': line.best_bookmaker,
            'bookmaker_count': line.source_count,
            'books': line.source_count,
            'odds_source': 'The Odds API',
            'decision': 'scanner_only',
        })
    return rows


def scan_to_frame(api_key: str, sports_to_scan: list[str], regions: str, markets: str, max_events: int, min_books: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for sport_key in sports_to_scan:
        try:
            summaries = scan_market(api_key, sport_key=sport_key, regions=regions, markets=markets, max_events=max_events)
            for summary in summaries:
                rows.extend(h2h_rows(summary))
                rows.extend(line_rows(summary, 'spreads', 'spreads'))
                rows.extend(line_rows(summary, 'totals', 'totals'))
        except Exception as exc:
            skipped.append({'sport_key': sport_key, 'error': str(exc)[:300]})
    frame = pd.DataFrame(rows)
    if not frame.empty and min_books > 1 and 'bookmaker_count' in frame.columns:
        frame = frame[pd.to_numeric(frame['bookmaker_count'], errors='coerce').fillna(0) >= min_books]
    st.session_state['scanner_pro_skipped'] = skipped
    return score_scanner_frame(frame)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))
api_key = get_secret('THE_ODDS_API_KEY', 'ODDS_API_KEY')
st.caption(f"{t('api_key')}: {'Configured' if api_key else 'Missing'}")
if not api_key:
    st.error(t('missing_key'))
    st.stop()

scope = st.radio(t('scan_scope'), [t('all_sports'), t('one_sport'), t('manual_sports')], horizontal=True)
regions = st.multiselect(t('regions'), ['us', 'eu', 'uk', 'au'], default=['us'])
markets = st.multiselect(t('markets'), ['h2h', 'spreads', 'totals'], default=['h2h'])
max_events = st.number_input(t('max_events'), min_value=1, max_value=100, value=20, step=5)
min_books = st.number_input(t('min_books'), min_value=1, max_value=20, value=1, step=1)
manual_keys = parse_manual_keys(st.text_input(t('manual_keys'), value='', help=t('manual_help')))

sports_df = pd.DataFrame(columns=['key', 'title', 'group', 'active'])
try:
    sports_df = pd.DataFrame([asdict(item) for item in list_sports(api_key, include_all=False)])
except Exception as exc:
    st.warning(f"{t('api_error')} Error: {str(exc)[:220]}")

search = st.text_input(t('sport_search'), value='')
if not sports_df.empty and search.strip():
    mask = sports_df.astype(str).agg(' '.join, axis=1).str.lower().str.contains(search.strip().lower(), regex=False, na=False)
    sports_df = sports_df[mask]

if scope == t('all_sports'):
    if sports_df.empty:
        sports_to_scan = manual_keys or DEFAULT_SPORT_KEYS[:2]
    else:
        max_sports = st.number_input(t('max_sports'), min_value=1, max_value=100, value=min(20, max(1, len(sports_df))), step=1)
        sports_to_scan = sports_df['key'].head(int(max_sports)).tolist() if 'key' in sports_df else []
elif scope == t('one_sport'):
    options = sports_df['key'].tolist() if 'key' in sports_df and not sports_df.empty else DEFAULT_SPORT_KEYS
    selected = st.multiselect(t('one_sport'), options=sorted(set(options + manual_keys)), default=(manual_keys or options[:1])[:3])
    sports_to_scan = selected
else:
    sports_to_scan = manual_keys or DEFAULT_SPORT_KEYS[:1]

with st.expander(t('sports'), expanded=False):
    if sports_df.empty:
        st.dataframe(pd.DataFrame({'key': DEFAULT_SPORT_KEYS, 'source': ['fallback_manual_option'] * len(DEFAULT_SPORT_KEYS)}), use_container_width=True, hide_index=True)
    else:
        st.dataframe(sports_df, use_container_width=True, hide_index=True)

if st.button(t('run'), type='primary', use_container_width=True):
    result = scan_to_frame(api_key, sports_to_scan, ','.join(regions), ','.join(markets), int(max_events), int(min_books))
    st.session_state['scanner_pro_latest_rows'] = result.to_dict('records')
    st.session_state['ara_latest_predictions'] = result.to_dict('records')
    st.session_state['ara_latest_predictions_source'] = 'Scanner Pro'
    st.session_state['ara_latest_predictions_saved_at'] = pd.Timestamp.utcnow().isoformat()
else:
    result = score_scanner_frame(pd.DataFrame(st.session_state.get('scanner_pro_latest_rows', [])))

if result.empty:
    st.warning(t('no_rows'))
    skipped = pd.DataFrame(st.session_state.get('scanner_pro_skipped', []))
    if not skipped.empty:
        st.subheader(t('skipped'))
        st.dataframe(skipped, use_container_width=True, hide_index=True)
    st.stop()

strength = scanner_strength_summary(result)
st.success(t('stored'))
cols = st.columns(7)
cols[0].metric(t('rows'), len(result))
cols[1].metric(t('sports'), result['sport_key'].nunique() if 'sport_key' in result else 0)
cols[2].metric(t('events'), result['event_id'].nunique() if 'event_id' in result else 0)
cols[3].metric(t('books'), round(float(pd.to_numeric(result.get('bookmaker_count', pd.Series(dtype=float)), errors='coerce').fillna(0).mean()), 2))
cols[4].metric(t('best_price_rows'), int(result.get('best_price', pd.Series(dtype=str)).fillna('').astype(str).str.strip().ne('').sum()) if 'best_price' in result else 0)
cols[5].metric(t('avg_strength'), 'N/A' if strength['avg_score'] is None else strength['avg_score'])
cols[6].metric(t('premium'), strength['premium_scan'])

st.subheader(t('top_scans'))
rank_cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'decimal_price', 'bookmaker', 'bookmaker_count', 'scanner_strength_score', 'scanner_strength_tier', 'scanner_recommendation', 'scanner_reasons'] if col in result.columns]
st.dataframe(result[rank_cols].head(50) if rank_cols else result.head(50), use_container_width=True, hide_index=True)

tabs = st.tabs([t('moneyline'), t('spreads'), t('totals'), 'All'])
with tabs[0]:
    st.dataframe(result[result['market_type'].eq('h2h')] if 'market_type' in result else result, use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(result[result['market_type'].eq('spreads')] if 'market_type' in result else pd.DataFrame(), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(result[result['market_type'].eq('totals')] if 'market_type' in result else pd.DataFrame(), use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(result, use_container_width=True, hide_index=True)

st.download_button(t('download'), result.to_csv(index=False), file_name='scanner_pro_live_markets.csv', mime='text/csv')

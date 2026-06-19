from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='What Are the Odds', layout='wide')
LANG = render_app_sidebar('what_are_the_odds', language_key='what_are_the_odds_pro_language', selector='radio')

TEXT = {
    'en': {
        'title': 'What Are the Odds',
        'caption': 'Manual review board. Enter one row, paste CSV text, or use latest Pro Predictor rows. The page saves rows automatically for the next tools.',
        'info': 'Mobile-safe mode: no button or file-upload button is required. Fill the single-game fields or paste CSV text, and the row/table saves automatically.',
        'workflow': 'Clean path: Pro Predictor → What Are the Odds → Odds Lock → Public Proof Dashboard → Learning Memory.',
        'single_game': 'Single Game Manual Check',
        'event': 'Game / event name',
        'sport': 'Sport / league',
        'market': 'Market type',
        'pick': 'Pick / prediction',
        'start': 'Event start UTC',
        'start_help': 'Use ISO format, for example 2026-06-17T23:10:00Z.',
        'decimal': 'Decimal price',
        'american': 'American price',
        'prob': 'Model probability %',
        'source': 'Source',
        'books': 'Source count',
        'notes': 'Notes',
        'session': 'Use latest Pro Predictor session rows',
        'paste_title': 'Mobile-safe CSV paste',
        'paste': 'Paste CSV text here',
        'paste_help': 'Paste the whole CSV including the header row. This avoids the mobile upload button completely.',
        'upload_optional': 'Optional desktop upload fallback',
        'upload': 'Upload CSV file(s)',
        'waiting': 'Fill event, pick, probability, and decimal or American price. Or paste CSV text / use latest session rows.',
        'saved': 'Rows are saved automatically for Odds Lock Pro and the public dashboard.',
        'download': 'Download analyzed rows',
    },
    'es': {
        'title': 'What Are the Odds',
        'caption': 'Tablero de revisión manual. Ingresa una fila, pega CSV o usa filas recientes de Predictor Pro. La página guarda automáticamente para las siguientes herramientas.',
        'info': 'Modo seguro para móvil: no se necesita botón ni botón de subida. Llena los campos o pega CSV y se guarda automáticamente.',
        'workflow': 'Ruta limpia: Predictor Pro → What Are the Odds → Odds Lock → Dashboard Público → Memoria.',
        'single_game': 'Revisión Manual de Un Solo Juego',
        'event': 'Juego / evento',
        'sport': 'Deporte / liga',
        'market': 'Tipo de mercado',
        'pick': 'Pick / pronóstico',
        'start': 'Inicio del evento UTC',
        'start_help': 'Usa formato ISO, por ejemplo 2026-06-17T23:10:00Z.',
        'decimal': 'Precio decimal',
        'american': 'Precio americano',
        'prob': 'Probabilidad del modelo %',
        'source': 'Fuente',
        'books': 'Número de fuentes',
        'notes': 'Notas',
        'session': 'Usar filas recientes de Predictor Pro',
        'paste_title': 'Pegar CSV seguro para móvil',
        'paste': 'Pega texto CSV aquí',
        'paste_help': 'Pega todo el CSV incluyendo encabezados. Esto evita completamente el botón móvil de subir archivo.',
        'upload_optional': 'Subida opcional para escritorio',
        'upload': 'Subir archivo(s) CSV',
        'waiting': 'Llena evento, pick, probabilidad y precio decimal o americano. O pega CSV / usa filas recientes.',
        'saved': 'Las filas se guardan automáticamente para Odds Lock Pro y el dashboard público.',
        'download': 'Descargar filas analizadas',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return default
    if pd.isna(parsed):
        return default
    return parsed


def decimal_from_american(value: Any) -> float | None:
    raw = safe_float(value)
    if raw is None or raw == 0:
        return None
    if raw > 0:
        return round(1.0 + raw / 100.0, 6)
    return round(1.0 + 100.0 / abs(raw), 6)


def probability_clean(value: Any) -> float | None:
    raw = safe_float(value)
    if raw is None or raw <= 0:
        return None
    if raw > 1:
        raw = raw / 100.0
    return round(max(0.0, min(1.0, raw)), 6)


def implied_probability(decimal_price: float | None) -> float | None:
    if decimal_price is None or decimal_price <= 1.0:
        return None
    return round(1.0 / decimal_price, 6)


def build_manual_row() -> dict[str, Any] | None:
    event = str(st.session_state.get('wato_event') or '').strip()
    pick = str(st.session_state.get('wato_pick') or '').strip()
    if not event or not pick:
        return None
    decimal_price = safe_float(st.session_state.get('wato_decimal'))
    american_price = safe_float(st.session_state.get('wato_american'))
    price = decimal_price if decimal_price and decimal_price > 1.0 else decimal_from_american(american_price)
    prob = probability_clean(st.session_state.get('wato_probability'))
    if prob is None or price is None:
        return None
    market_prob = implied_probability(price)
    edge = round(prob - market_prob, 6) if market_prob is not None else None
    ev = round(prob * price - 1.0, 6)
    score = round(max(0.0, min(100.0, prob * 70.0 + max(-10.0, min(25.0, (edge or 0) * 300.0)) + 5.0)), 2)
    return {
        'event': event,
        'sport': str(st.session_state.get('wato_sport') or '').strip() or 'manual_single_game',
        'market_type': str(st.session_state.get('wato_market') or 'h2h'),
        'prediction': pick,
        'event_start_utc': str(st.session_state.get('wato_start') or '').strip(),
        'model_probability': prob,
        'model_probability_clean': prob,
        'decimal_price': round(float(price), 6),
        'american_odds': american_price if american_price not in (None, 0) else '',
        'market_implied_probability': market_prob if market_prob is not None else '',
        'model_market_edge': edge if edge is not None else '',
        'edge_percent': round(edge * 100.0, 2) if edge is not None else '',
        'expected_value_per_unit': ev,
        'expected_value_percent': round(ev * 100.0, 2),
        'bookmaker': str(st.session_state.get('wato_bookmaker') or '').strip() or 'manual_source',
        'odds_source': str(st.session_state.get('wato_bookmaker') or '').strip() or 'manual_source',
        'bookmaker_count': int(st.session_state.get('wato_books') or 1),
        'books': int(st.session_state.get('wato_books') or 1),
        'manual_context_notes': str(st.session_state.get('wato_notes') or '').strip(),
        'single_game_manual': True,
        'source_file': 'single_game_manual_check',
        'agent_decision': 'play_strong' if ev > 0 and prob >= 0.58 else 'research_watch',
        'agent_score': score,
        'scanner_strength_score': score,
        'recommended_action': 'review_and_route',
        'lock_ready': bool(str(st.session_state.get('wato_start') or '').strip()),
        'result_status': 'pending',
    }


def load_session_rows() -> pd.DataFrame:
    if not st.session_state.get('wato_use_session'):
        return pd.DataFrame()
    for key in ['pro_predictor_high_confidence_rows', 'pro_predictor_latest_rows', 'ara_latest_predictions']:
        rows = st.session_state.get(key) or []
        if rows:
            return pd.DataFrame(rows)
    return pd.DataFrame()


def load_pasted_rows() -> pd.DataFrame:
    pasted = str(st.session_state.get('wato_pasted_csv') or '').strip()
    if not pasted:
        return pd.DataFrame()
    try:
        frame = pd.read_csv(StringIO(pasted))
        frame['source_file'] = 'pasted_csv_mobile_safe'
        return frame
    except Exception as exc:
        st.warning(f'Pasted CSV could not be read: {exc}')
        return pd.DataFrame()


def load_optional_uploads() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    with st.expander(t('upload_optional'), expanded=False):
        uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
        if uploads:
            for upload in uploads:
                try:
                    frame = pd.read_csv(upload)
                    frame['source_file'] = upload.name
                    frames.append(frame)
                except Exception as exc:
                    st.warning(f'CSV could not be read: {exc}')
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def save_rows(frame: pd.DataFrame) -> None:
    rows = frame.to_dict('records')
    for key in ['what_are_the_odds_latest_rows', 'ara_latest_predictions', 'odds_lock_pro_candidate_rows', 'public_proof_dashboard_refresh_rows']:
        st.session_state[key] = rows
    try:
        from autonomous_betting_agent.pick_hold_store import save_held_rows
        workspace_id = str(st.session_state.get('aba_test_window_id') or 'test_01')
        save_held_rows('what_are_the_odds_latest_rows', rows, workspace_id)
        save_held_rows('ara_latest_predictions', rows, workspace_id)
    except Exception:
        pass


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))
st.caption(t('workflow'))

st.subheader(t('single_game'))
st.text_input(t('event'), key='wato_event', placeholder='Los Angeles Dodgers at San Diego Padres')
st.text_input(t('pick'), key='wato_pick', placeholder='Los Angeles Dodgers')
c1, c2, c3 = st.columns(3)
c1.text_input(t('sport'), key='wato_sport', placeholder='MLB, NBA, WNBA, Soccer, Tennis')
c2.selectbox(t('market'), ['h2h', 'spreads', 'totals', 'prop', 'other'], key='wato_market')
c3.text_input(t('start'), key='wato_start', placeholder='2026-06-17T23:10:00Z', help=t('start_help'))
c4, c5, c6, c7 = st.columns(4)
c4.number_input(t('decimal'), min_value=0.0, max_value=1000.0, value=0.0, step=0.01, key='wato_decimal')
c5.number_input(t('american'), min_value=-5000.0, max_value=5000.0, value=0.0, step=5.0, key='wato_american')
c6.number_input(t('prob'), min_value=0.0, max_value=100.0, value=0.0, step=0.5, key='wato_probability')
c7.number_input(t('books'), min_value=0, max_value=100, value=1, step=1, key='wato_books')
st.text_input(t('source'), key='wato_bookmaker', placeholder='DraftKings / FanDuel / Bet365')
st.text_area(t('notes'), key='wato_notes', height=100, placeholder='Context notes')
st.checkbox(t('session'), value=False, key='wato_use_session')

st.subheader(t('paste_title'))
st.text_area(t('paste'), key='wato_pasted_csv', height=160, help=t('paste_help'), placeholder='event,prediction,model_probability,decimal_price\nTeam A at Team B,Team A,0.61,1.91')
optional_uploads = load_optional_uploads()

frames: list[pd.DataFrame] = []
manual = build_manual_row()
if manual is not None:
    frames.append(pd.DataFrame([manual]))
session_frame = load_session_rows()
if not session_frame.empty:
    frames.append(session_frame)
pasted_frame = load_pasted_rows()
if not pasted_frame.empty:
    frames.append(pasted_frame)
if not optional_uploads.empty:
    frames.append(optional_uploads)

if not frames:
    st.warning(t('waiting'))
    st.stop()

output = pd.concat(frames, ignore_index=True, sort=False)
save_rows(output)
st.success(t('saved'))
st.dataframe(output, use_container_width=True, hide_index=True)
st.download_button(t('download'), output.to_csv(index=False), file_name='what_are_the_odds_analyzed_rows.csv', mime='text/csv', use_container_width=True)

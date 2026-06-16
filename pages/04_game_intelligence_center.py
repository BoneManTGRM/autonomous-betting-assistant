from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import build_agent_decisions
from autonomous_betting_agent.game_intelligence_tools import (
    agent_answer,
    display_columns,
    enrich_game_intelligence,
    line_shop_table,
    operator_daily_report,
    shadow_proof_frame,
)
from autonomous_betting_agent.odds_accuracy_tools import enrich_odds_accuracy
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.scanner_strength import score_scanner_frame
from autonomous_betting_agent.tool_sidebar import render_tool_sidebar

st.set_page_config(page_title='Game Intelligence Center', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='game_intelligence_language') == 'Español' else 'en'
render_tool_sidebar('what_are_the_odds', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Game Intelligence Center',
        'caption': 'Field-first single-game review, line shopping, minimum playable odds, information confidence, market disagreement checks, data quality wall, Q&A, shadow proof, and operator report.',
        'single': 'Single-game fields',
        'bulk': 'Advanced bulk input',
        'use_session': 'Use latest session rows',
        'upload': 'Upload CSV file(s)',
        'paste': 'Paste CSV text',
        'event': 'Game / event name',
        'sport': 'Sport / league',
        'market': 'Market type',
        'pick': 'Pick / prediction',
        'start': 'Event start UTC',
        'bookmaker': 'Main bookmaker / source',
        'decimal': 'Main decimal odds',
        'american': 'American odds',
        'prob': 'Model probability %',
        'books': 'Book count',
        'notes': 'Notes',
        'line_shop': 'Line shopping prices',
        'analyze': 'Analyze single game',
        'missing': 'Enter at least event, pick, probability, and decimal or American odds.',
        'loaded': 'Single game loaded.',
        'board': 'Intelligence board',
        'card': 'Game card',
        'line_tab': 'Line shopping',
        'ask': 'Ask the agent',
        'quality': 'Data quality wall',
        'shadow': 'Shadow proof',
        'report': 'Daily report',
        'question': 'Question about selected game',
        'no_rows': 'No rows available. Fill the single-game form, use session rows, upload a CSV, or paste CSV text.',
    },
    'es': {
        'title': 'Centro de Inteligencia de Juego',
        'caption': 'Revisión de un juego con campos, line shopping, cuota mínima jugable, confianza de información, desacuerdo de mercado, pared de calidad, Q&A, shadow proof y reporte diario.',
        'single': 'Campos de un solo juego',
        'bulk': 'Entrada masiva avanzada',
        'use_session': 'Usar últimas filas de sesión',
        'upload': 'Subir CSV(s)',
        'paste': 'Pegar CSV',
        'event': 'Juego / evento',
        'sport': 'Deporte / liga',
        'market': 'Tipo de mercado',
        'pick': 'Pick / pronóstico',
        'start': 'Inicio del evento UTC',
        'bookmaker': 'Casa / fuente principal',
        'decimal': 'Cuota decimal principal',
        'american': 'Cuota americana',
        'prob': 'Probabilidad del modelo %',
        'books': 'Número de casas',
        'notes': 'Notas',
        'line_shop': 'Precios line shopping',
        'analyze': 'Analizar juego',
        'missing': 'Ingresa evento, pick, probabilidad y cuota decimal o americana.',
        'loaded': 'Juego cargado.',
        'board': 'Tablero de inteligencia',
        'card': 'Tarjeta del juego',
        'line_tab': 'Line shopping',
        'ask': 'Preguntar al agente',
        'quality': 'Pared de calidad',
        'shadow': 'Shadow proof',
        'report': 'Reporte diario',
        'question': 'Pregunta sobre el juego seleccionado',
        'no_rows': 'No hay filas. Llena el formulario, usa sesión, sube CSV o pega CSV.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def num(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def decimal_from_american(value: Any) -> float | None:
    odds = num(value)
    if odds is None:
        return None
    if odds >= 100:
        return round(1.0 + odds / 100.0, 6)
    if odds <= -100:
        return round(1.0 + 100.0 / abs(odds), 6)
    return None


def session_frame() -> pd.DataFrame:
    frames = []
    for key in ['what_are_the_odds_latest_rows', 'pro_predictor_latest_rows', 'pro_predictor_high_confidence_rows', 'scanner_pro_latest_rows']:
        rows = st.session_state.get(key) or []
        if rows:
            frame = pd.DataFrame(rows)
            frame['session_source'] = key
            frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def single_game_form() -> pd.DataFrame:
    st.subheader(t('single'))
    with st.form('game_intelligence_single_form', clear_on_submit=False):
        top = st.columns(2)
        event = top[0].text_input(t('event'), placeholder='Los Angeles Dodgers at San Diego Padres')
        sport = top[1].text_input(t('sport'), placeholder='MLB')
        mid = st.columns(4)
        market = mid[0].selectbox(t('market'), ['h2h', 'spreads', 'totals', 'prop', 'other'])
        pick = mid[1].text_input(t('pick'), placeholder='Los Angeles Dodgers')
        start = mid[2].text_input(t('start'), placeholder='2026-06-17T23:10:00Z')
        bookmaker = mid[3].text_input(t('bookmaker'), placeholder='DraftKings')
        odds = st.columns(5)
        decimal = odds[0].number_input(t('decimal'), min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        american = odds[1].number_input(t('american'), min_value=-5000.0, max_value=5000.0, value=0.0, step=5.0)
        probability = odds[2].number_input(t('prob'), min_value=0.0, max_value=100.0, value=0.0, step=0.5)
        books = odds[3].number_input(t('books'), min_value=0, max_value=100, value=1, step=1)
        closing = odds[4].number_input('Closing decimal price', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        st.caption(t('line_shop'))
        book_cols = st.columns(5)
        dk = book_cols[0].number_input('DraftKings', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        fd = book_cols[1].number_input('FanDuel', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        bet365 = book_cols[2].number_input('Bet365', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        pinnacle = book_cols[3].number_input('Pinnacle', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        local = book_cols[4].number_input('Local/Other', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        notes = st.text_area(t('notes'), placeholder='Starter confirmed; no major injuries; weather normal; price still playable')
        submitted = st.form_submit_button(t('analyze'), use_container_width=True)
    if not submitted:
        return pd.DataFrame()
    price = float(decimal) if float(decimal) > 1.0 else decimal_from_american(american)
    prob = float(probability) / 100.0 if float(probability) > 1.0 else float(probability)
    if not event.strip() or not pick.strip() or price is None or not (0.0 < prob < 1.0):
        st.warning(t('missing'))
        return pd.DataFrame()
    row = {
        'event': event.strip(), 'sport': sport.strip() or 'manual_single_game', 'market_type': market,
        'prediction': pick.strip(), 'event_start_utc': start.strip(), 'bookmaker': bookmaker.strip() or 'manual_source',
        'odds_source': bookmaker.strip() or 'manual_source', 'decimal_price': price, 'model_probability': round(prob, 6),
        'model_probability_clean': round(prob, 6), 'bookmaker_count': int(books), 'books': int(books),
        'closing_decimal_price': round(float(closing), 6) if float(closing) > 1.0 else '',
        'draftkings_decimal_price': dk if dk > 1 else '', 'fanduel_decimal_price': fd if fd > 1 else '',
        'bet365_decimal_price': bet365 if bet365 > 1 else '', 'pinnacle_decimal_price': pinnacle if pinnacle > 1 else '',
        'local_decimal_price': local if local > 1 else '', 'manual_context_notes': notes.strip(),
        'single_game_manual': True, 'source_file': 'game_intelligence_center', 'result_status': 'pending',
    }
    st.success(t('loaded'))
    return pd.DataFrame([row])


def read_inputs() -> pd.DataFrame:
    frames = []
    single = single_game_form()
    if not single.empty:
        frames.append(single)
    if st.checkbox(t('use_session'), value=bool(st.session_state.get('what_are_the_odds_latest_rows') or st.session_state.get('pro_predictor_latest_rows'))):
        session = session_frame()
        if not session.empty:
            frames.append(session)
    with st.expander(t('bulk'), expanded=False):
        uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
        if uploads:
            for upload in uploads:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                frames.append(frame)
        pasted = st.text_area(t('paste'), height=120)
        if pasted.strip():
            frame = pd.read_csv(StringIO(pasted.strip()))
            frame['source_file'] = 'pasted_csv'
            frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_frame(frame)
    odds = enrich_odds_accuracy(normalized)
    scored = score_scanner_frame(odds)
    decisions = build_agent_decisions(scored)
    decisions = score_scanner_frame(decisions)
    return enrich_game_intelligence(decisions)


st.title(t('title'))
st.caption(t('caption'))
raw = read_inputs()
if raw.empty:
    st.warning(t('no_rows'))
    st.stop()

board = prepare(raw)
st.session_state['game_intelligence_latest_rows'] = board.to_dict('records')
st.session_state['what_are_the_odds_latest_rows'] = board.to_dict('records')
st.session_state['ara_latest_predictions'] = board.to_dict('records')

cols = st.columns(6)
cols[0].metric('Rows', len(board))
cols[1].metric('Shadow candidates', int(board.get('shadow_proof_ready', pd.Series(dtype=bool)).fillna(False).astype(bool).sum()))
cols[2].metric('Quality pass', int(board.get('data_quality_wall_pass', pd.Series(dtype=bool)).fillna(False).astype(bool).sum()))
cols[3].metric('A/A+', int(board.get('game_intelligence_grade', pd.Series(dtype=str)).astype(str).str.contains('A').sum()))
cols[4].metric('Review', int(board.get('data_quality_wall_pass', pd.Series(dtype=bool)).fillna(False).astype(bool).eq(False).sum()))
cols[5].metric('Line shops', int(board.get('line_shop_count', pd.Series(dtype=float)).fillna(0).sum()))

options = [f"{row.get('prediction', 'Pick')} — {row.get('event', 'Event')}" for row in board.to_dict(orient='records')]
selected_label = st.selectbox('Selected game', options)
selected_index = options.index(selected_label)
selected = board.iloc[selected_index].to_dict()

tabs = st.tabs([t('card'), t('board'), t('line_tab'), t('ask'), t('quality'), t('shadow'), t('report')])
with tabs[0]:
    st.markdown(selected.get('game_intelligence_card', 'No card available.'))
with tabs[1]:
    cols_to_show = display_columns(board)
    st.dataframe(board[cols_to_show] if cols_to_show else board, use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(line_shop_table(selected), use_container_width=True, hide_index=True)
with tabs[3]:
    question = st.text_input(t('question'), placeholder='Why is this not ready? What odds do I need? What would change your mind?')
    st.write(agent_answer(selected, question))
with tabs[4]:
    quality_cols = [col for col in ['event', 'prediction', 'data_quality_wall_pass', 'data_quality_blockers', 'data_quality_warnings', 'information_confidence_score', 'market_disagreement_flag', 'what_would_change_my_mind'] if col in board.columns]
    st.dataframe(board[quality_cols], use_container_width=True, hide_index=True)
with tabs[5]:
    shadow = shadow_proof_frame(board)
    st.dataframe(shadow, use_container_width=True, hide_index=True)
    st.download_button('Download shadow proof CSV', shadow.to_csv(index=False), file_name='shadow_proof_internal.csv', mime='text/csv')
with tabs[6]:
    report = operator_daily_report(board)
    st.text_area(t('report'), value=report, height=420)
    st.download_button('Download operator report', report, file_name='daily_operator_report.md', mime='text/markdown')

st.download_button('Download intelligence board CSV', board.to_csv(index=False), file_name='game_intelligence_board.csv', mime='text/csv')

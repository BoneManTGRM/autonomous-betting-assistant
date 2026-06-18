from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

st.set_page_config(page_title='ABA Signal Board', layout='wide')

LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='signal_board_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'ABA Signal Board',
        'caption': 'One-page workflow: review the best Pro Predictor rows, bucket them, send them to odds/value review or proof locking, then track results.',
        'no_rows': 'No prediction rows found yet. Run Pro Predictor first, then come back here.',
        'source': 'Source',
        'rows': 'Rows',
        'tier_a': 'Tier A — strongest candidates',
        'tier_b': 'Tier B — high-confidence test',
        'tier_c': 'Tier C — research volume',
        'all_rows': 'All rows',
        'actions': 'Actions',
        'send_all_lock': 'Send A/B/C to Odds Lock Pro',
        'send_a_lock': 'Send Tier A only to Odds Lock Pro',
        'send_odds': 'Send current board to What Are the Odds',
        'sent': 'Rows saved in session. Open the target page from the links below.',
        'open_predictor': 'Open Pro Predictor',
        'open_odds': 'Open What Are the Odds',
        'open_lock': 'Open Odds Lock Pro',
        'open_threshold': 'Open Threshold Optimizer',
        'download': 'Download current signal board CSV',
        'guide': 'Simple workflow',
        'guide_text': '1) Run Pro Predictor. 2) Review this Signal Board. 3) Send A/B/C to Research/Test locking. 4) Grade results. 5) Use Threshold Optimizer to learn which buckets are winning.',
    },
    'es': {
        'title': 'ABA Signal Board',
        'caption': 'Flujo de una página: revisa las mejores filas de Predictor Pro, clasifícalas, envíalas a revisión de cuotas/valor o bloqueo de prueba, y mide resultados.',
        'no_rows': 'Aún no hay predicciones. Ejecuta Predictor Pro primero y vuelve aquí.',
        'source': 'Fuente',
        'rows': 'Filas',
        'tier_a': 'Tier A — candidatos más fuertes',
        'tier_b': 'Tier B — prueba de alta confianza',
        'tier_c': 'Tier C — volumen de investigación',
        'all_rows': 'Todas las filas',
        'actions': 'Acciones',
        'send_all_lock': 'Enviar A/B/C a Odds Lock Pro',
        'send_a_lock': 'Enviar solo Tier A a Odds Lock Pro',
        'send_odds': 'Enviar tablero a What Are the Odds',
        'sent': 'Filas guardadas en la sesión. Abre la página destino con los enlaces abajo.',
        'open_predictor': 'Abrir Predictor Pro',
        'open_odds': 'Abrir What Are the Odds',
        'open_lock': 'Abrir Odds Lock Pro',
        'open_threshold': 'Abrir Optimizador de Umbrales',
        'download': 'Descargar CSV del tablero actual',
        'guide': 'Flujo simple',
        'guide_text': '1) Ejecuta Predictor Pro. 2) Revisa este Signal Board. 3) Envía A/B/C al bloqueo Investigación/Prueba. 4) Califica resultados. 5) Usa el Optimizador para aprender qué buckets ganan.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def session_source() -> tuple[str, pd.DataFrame]:
    sources = [
        ('pro_predictor_high_confidence_rows', 'Pro Predictor high-confidence'),
        ('pro_predictor_latest_rows', 'Pro Predictor latest'),
        ('what_are_the_odds_latest_rows', 'What Are the Odds'),
        ('ara_latest_predictions', 'Latest session'),
    ]
    for key, label in sources:
        rows = st.session_state.get(key) or []
        if rows:
            return label, pd.DataFrame(rows)
    return '', pd.DataFrame()


def num(frame: pd.DataFrame, names: list[str]) -> pd.Series:
    for name in names:
        if name in frame.columns:
            values = pd.to_numeric(frame[name], errors='coerce')
            if values.notna().any():
                if 'prob' in name.lower():
                    values = values.where(values <= 1.0, values / 100.0)
                return values
    return pd.Series(index=frame.index, dtype=float)


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    out['_prob'] = num(out, ['model_probability_clean', 'model_probability', 'final_probability_value', 'probability']).reindex(out.index)
    out['_edge'] = num(out, ['model_market_edge', 'model_edge', 'edge', 'computed_ev_decimal', 'estimated_ev_decimal']).reindex(out.index)
    out['_signal'] = num(out, ['scanner_strength_score', 'signal_strength_score']).reindex(out.index)
    out['_agent'] = num(out, ['agent_score']).reindex(out.index)
    out['_books'] = num(out, ['bookmaker_count', 'books', 'source_count']).reindex(out.index)
    out['_api'] = num(out, ['api_coverage_score', 'api_coverage']).reindex(out.index)
    out['_price'] = num(out, ['decimal_price', 'best_price', 'average_price']).reindex(out.index)

    risk = pd.Series(0, index=out.index, dtype=int)
    risk += out['_books'].fillna(0).lt(4).astype(int)
    risk += out['_api'].fillna(0).lt(0.50).astype(int)
    risk += out['_agent'].fillna(0).lt(60).astype(int)
    risk += out['_signal'].fillna(0).lt(45).astype(int)
    risk += out['_edge'].fillna(-1).lt(0).astype(int)
    out['confidence_risk_score'] = risk

    out['confidence_bucket'] = 'C_research_volume'
    tier_b = out['_prob'].fillna(0).ge(0.58) & out['_signal'].fillna(0).ge(38) & out['_agent'].fillna(0).ge(35) & risk.le(3)
    tier_a = out['_prob'].fillna(0).ge(0.60) & out['_signal'].fillna(0).ge(40) & out['_agent'].fillna(0).ge(40) & risk.le(1)
    out.loc[tier_b, 'confidence_bucket'] = 'B_high_confidence_test'
    out.loc[tier_a, 'confidence_bucket'] = 'A_top_candidate'
    out['odds_ready'] = out['_price'].fillna(0).gt(1.0)

    sort_cols = ['confidence_risk_score', '_prob', '_signal', '_agent', '_edge']
    out = out.sort_values(sort_cols, ascending=[True, False, False, False, False], na_position='last').reset_index(drop=True)
    return out.drop(columns=[col for col in ['_prob', '_edge', '_signal', '_agent', '_books', '_api', '_price'] if col in out.columns], errors='ignore')


def show_table(frame: pd.DataFrame) -> None:
    cols = [col for col in [
        'confidence_bucket', 'confidence_risk_score', 'event', 'sport', 'market_type', 'prediction',
        'model_probability_clean', 'model_probability', 'model_market_edge', 'decimal_price', 'bookmaker',
        'bookmaker_count', 'api_coverage_score', 'agent_decision', 'agent_score', 'scanner_strength_score',
        'lock_ready', 'decision_reasons'
    ] if col in frame.columns]
    st.dataframe(frame[cols] if cols else frame, use_container_width=True, hide_index=True)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('guide_text'))
source, raw = session_source()

if raw.empty:
    st.warning(t('no_rows'))
    st.page_link('pages/pro_predictor.py', label=t('open_predictor'))
    st.stop()

board = enrich(raw)
counts = board['confidence_bucket'].value_counts().to_dict() if 'confidence_bucket' in board.columns else {}
metrics = st.columns(5)
metrics[0].metric(t('source'), source)
metrics[1].metric(t('rows'), len(board))
metrics[2].metric('Tier A', int(counts.get('A_top_candidate', 0)))
metrics[3].metric('Tier B', int(counts.get('B_high_confidence_test', 0)))
metrics[4].metric('Tier C', int(counts.get('C_research_volume', 0)))

tabs = st.tabs([t('tier_a'), t('tier_b'), t('tier_c'), t('all_rows'), t('actions')])
with tabs[0]:
    show_table(board[board['confidence_bucket'].eq('A_top_candidate')])
with tabs[1]:
    show_table(board[board['confidence_bucket'].eq('B_high_confidence_test')])
with tabs[2]:
    show_table(board[board['confidence_bucket'].eq('C_research_volume')])
with tabs[3]:
    show_table(board)
    st.download_button(t('download'), board.to_csv(index=False), file_name='aba_signal_board.csv', mime='text/csv')
with tabs[4]:
    st.subheader(t('actions'))
    a_rows = board[board['confidence_bucket'].eq('A_top_candidate')]
    if st.button(t('send_all_lock'), use_container_width=True):
        st.session_state['pro_predictor_latest_rows'] = board.to_dict('records')
        st.session_state['pro_predictor_high_confidence_rows'] = board.to_dict('records')
        st.session_state['ara_latest_predictions'] = board.to_dict('records')
        st.success(t('sent'))
    if st.button(t('send_a_lock'), use_container_width=True):
        st.session_state['pro_predictor_latest_rows'] = a_rows.to_dict('records')
        st.session_state['pro_predictor_high_confidence_rows'] = a_rows.to_dict('records')
        st.session_state['ara_latest_predictions'] = a_rows.to_dict('records')
        st.success(t('sent'))
    if st.button(t('send_odds'), use_container_width=True):
        st.session_state['what_are_the_odds_latest_rows'] = board.to_dict('records')
        st.session_state['ara_latest_predictions'] = board.to_dict('records')
        st.success(t('sent'))
    st.page_link('pages/pro_predictor.py', label=t('open_predictor'))
    st.page_link('pages/what_are_the_odds.py', label=t('open_odds'))
    st.page_link('pages/odds_lock_pro.py', label=t('open_lock'))
    st.page_link('pages/threshold_optimizer.py', label=t('open_threshold'))

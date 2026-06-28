from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.pick_hold_store import (
    load_first_available,
    normalize_workspace_id,
    rows_from_any,
    save_held_rows,
)
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title='ABA Signal Board', layout='wide')
LANG = render_app_sidebar('signal_board', language_key='signal_board_language', selector='radio')

HANDOFF_SOURCES = [
    ('pro_predictor_high_confidence_rows', 'pro_predictor_high_confidence'),
    ('pro_predictor_latest_rows', 'pro_predictor_latest'),
    ('what_are_the_odds_latest_rows', 'what_are_the_odds'),
    ('ara_latest_predictions', 'latest_predictions'),
]

TEXT = {
    'en': {
        'title': 'ABA Signal Board',
        'caption': 'Review Pro Predictor rows, bucket them, send them to odds/value review or proof locking, then track results.',
        'no_rows': 'No prediction rows found in session or durable storage. Run Pro Predictor first, then come back here.',
        'source': 'Source',
        'rows': 'Rows',
        'workspace': 'Workspace ID',
        'durable_loaded': 'Loaded saved rows from durable storage.',
        'tier_a': 'Tier A — strongest candidates',
        'tier_b': 'Tier B — high-confidence test',
        'tier_c': 'Tier C — research volume',
        'tier_a_metric': 'Tier A',
        'tier_b_metric': 'Tier B',
        'tier_c_metric': 'Tier C',
        'all_rows': 'All rows',
        'actions': 'Actions',
        'send_all_lock': 'Send A/B/C to Odds Lock Pro',
        'send_a_lock': 'Send Tier A only to Odds Lock Pro',
        'send_odds': 'Send current board to What Are the Odds',
        'sent': 'Rows saved to session and durable handoff storage. Open the target page from the Tools menu.',
        'open_predictor': 'Open Pro Predictor',
        'open_odds': 'Open What Are the Odds',
        'open_lock': 'Open Odds Lock Pro',
        'open_threshold': 'Open Threshold Optimizer',
        'download': 'Download current signal board CSV',
        'guide_text': '1) Run Pro Predictor. 2) Review this Signal Board. 3) Send A/B/C to Research/Test locking. 4) Grade results. 5) Use Threshold Optimizer to learn which buckets are winning.',
        'source_pro_predictor_high_confidence': 'Pro Predictor high-confidence',
        'source_pro_predictor_latest': 'Pro Predictor latest',
        'source_what_are_the_odds': 'What Are the Odds',
        'source_latest_predictions': 'Latest predictions',
        'durable_suffix': 'durable',
    },
    'es': {
        'title': 'ABA Signal Board',
        'caption': 'Revisa filas de Predictor Pro, clasificalas, envialas a revision de cuotas/prueba y mide resultados.',
        'no_rows': 'No hay predicciones en sesion ni en almacenamiento guardado. Ejecuta Predictor Pro primero y vuelve aqui.',
        'source': 'Fuente',
        'rows': 'Filas',
        'workspace': 'ID de workspace',
        'durable_loaded': 'Filas guardadas cargadas desde almacenamiento guardado.',
        'tier_a': 'Nivel A - candidatos mas fuertes',
        'tier_b': 'Nivel B - prueba de alta confianza',
        'tier_c': 'Nivel C - volumen de investigacion',
        'tier_a_metric': 'Nivel A',
        'tier_b_metric': 'Nivel B',
        'tier_c_metric': 'Nivel C',
        'all_rows': 'Todas las filas',
        'actions': 'Acciones',
        'send_all_lock': 'Enviar A/B/C a Odds Lock Pro',
        'send_a_lock': 'Enviar solo Nivel A a Odds Lock Pro',
        'send_odds': 'Enviar tablero a revision de cuotas',
        'sent': 'Filas guardadas en sesion y almacenamiento de traspaso. Abre la pagina destino desde el menu de herramientas.',
        'open_predictor': 'Abrir Predictor Pro',
        'open_odds': 'Abrir revision de cuotas',
        'open_lock': 'Abrir Odds Lock Pro',
        'open_threshold': 'Abrir Optimizador de Umbrales',
        'download': 'Descargar CSV del tablero actual',
        'guide_text': '1) Ejecuta Predictor Pro. 2) Revisa este tablero de senales. 3) Envia A/B/C al bloqueo investigacion/prueba. 4) Califica resultados. 5) Usa el optimizador para aprender que niveles ganan.',
        'source_pro_predictor_high_confidence': 'Predictor Pro alta confianza',
        'source_pro_predictor_latest': 'Predicciones recientes de Predictor Pro',
        'source_what_are_the_odds': 'Revision de cuotas',
        'source_latest_predictions': 'Predicciones recientes',
        'durable_suffix': 'almacenamiento guardado',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def source_label(label_key: str) -> str:
    return t(f'source_{label_key}')


def go_to(path: str) -> None:
    try:
        st.switch_page(path)
    except Exception:
        st.page_link(path, label=path)


def records_from(value: Any) -> list[dict[str, Any]]:
    return rows_from_any(value)


def frame_from_records(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def session_source(workspace_id: str) -> tuple[str, pd.DataFrame]:
    for key, label_key in HANDOFF_SOURCES:
        rows = records_from(st.session_state.get(key))
        if rows:
            return source_label(label_key), frame_from_records(rows)

    key, rows = load_first_available([key for key, _label_key in HANDOFF_SOURCES], workspace_id)
    if rows:
        st.session_state[key] = rows
        label_key = next((source_label_key for source_key, source_label_key in HANDOFF_SOURCES if source_key == key), key)
        return f'{source_label(label_key)} · {t("durable_suffix")}', frame_from_records(rows)

    return '', pd.DataFrame()


def persist_handoff(frame: pd.DataFrame, keys: list[str], workspace_id: str) -> int:
    records = frame.to_dict('records')
    saved = 0
    for key in keys:
        st.session_state[key] = records
        saved = max(saved, save_held_rows(key, records, workspace_id))
        if workspace_id != 'test_01':
            save_held_rows(key, records, 'test_01')
    return saved


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
    display = frame[cols] if cols else frame
    st.dataframe(localize_dataframe(display, LANG), use_container_width=True, hide_index=True)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('guide_text'))

workspace_default = normalize_workspace_id(st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(st.text_input(t('workspace'), value=workspace_default))
st.session_state['aba_test_window_id'] = workspace_id

source, raw = session_source(workspace_id)

if raw.empty:
    st.warning(t('no_rows'))
    if st.button(t('open_predictor'), type='primary', use_container_width=True):
        go_to('pages/pro_predictor.py')
    st.stop()

if t('durable_suffix') in source.lower():
    st.success(t('durable_loaded'))

board = enrich(raw)
counts = board['confidence_bucket'].value_counts().to_dict() if 'confidence_bucket' in board.columns else {}
metrics = st.columns(5)
metrics[0].metric(t('source'), source)
metrics[1].metric(t('rows'), len(board))
metrics[2].metric(t('tier_a_metric'), int(counts.get('A_top_candidate', 0)))
metrics[3].metric(t('tier_b_metric'), int(counts.get('B_high_confidence_test', 0)))
metrics[4].metric(t('tier_c_metric'), int(counts.get('C_research_volume', 0)))

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
        persist_handoff(
            board,
            ['pro_predictor_latest_rows', 'pro_predictor_high_confidence_rows', 'ara_latest_predictions'],
            workspace_id,
        )
        st.success(t('sent'))
    if st.button(t('send_a_lock'), use_container_width=True):
        persist_handoff(
            a_rows,
            ['pro_predictor_latest_rows', 'pro_predictor_high_confidence_rows', 'ara_latest_predictions'],
            workspace_id,
        )
        st.success(t('sent'))
    if st.button(t('send_odds'), use_container_width=True):
        persist_handoff(
            board,
            ['what_are_the_odds_latest_rows', 'ara_latest_predictions'],
            workspace_id,
        )
        st.success(t('sent'))
    col1, col2 = st.columns(2)
    if col1.button(t('open_predictor'), type='primary', use_container_width=True):
        go_to('pages/pro_predictor.py')
    if col2.button(t('open_odds'), use_container_width=True):
        go_to('pages/what_are_the_odds.py')
    col3, col4 = st.columns(2)
    if col3.button(t('open_lock'), use_container_width=True):
        go_to('pages/odds_lock_pro.py')
    if col4.button(t('open_threshold'), use_container_width=True):
        go_to('pages/threshold_optimizer.py')

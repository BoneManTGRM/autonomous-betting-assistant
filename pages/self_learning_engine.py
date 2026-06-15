from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import agent_decision_summary, build_agent_decisions, lock_ready_candidates, playable_candidates
from autonomous_betting_agent.api_snapshot_memory import build_api_snapshots, export_snapshot_manifest, snapshot_memory_summary
from autonomous_betting_agent.clv_intelligence import build_clv_intelligence, clv_by_segment, clv_summary
from autonomous_betting_agent.post_loss_autopsy import autopsy_summary, build_loss_autopsies, future_rules
from autonomous_betting_agent.row_normalizer import normalize_frame, result_status, safe_text
from autonomous_betting_agent.sport_specific_models import build_sport_specific_decisions, sport_model_summary
from autonomous_betting_agent.walk_forward_lab import walk_forward_summary, walk_forward_validate

st.set_page_config(page_title='Learning Memory Studio', layout='wide')

TRACKER_COLUMNS = ['event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price', 'bookmaker', 'odds_source', 'prediction_timestamp', 'event_start_utc', 'confidence_tier', 'result_status', 'winner', 'final_score', 'closing_decimal_price', 'stake_units', 'profit_units', 'notes']
RESULT_MAP = {
    'won': 'win', 'win': 'win', 'w': 'win', 'correct': 'win', 'hit': 'win', 'ganó': 'win', 'gano': 'win',
    'lost': 'loss', 'loss': 'loss', 'l': 'loss', 'incorrect': 'loss', 'miss': 'loss', 'perdió': 'loss', 'perdio': 'loss',
    'void': 'void', 'push': 'void', 'cancelled': 'void', 'canceled': 'void',
    'unknown': 'pending', 'pending': 'pending', 'scheduled': 'pending', 'live': 'pending', '': 'pending',
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def clean_result(value: Any) -> str:
    text = safe_text(value).lower()
    return RESULT_MAP.get(text, result_status({'result_status': text}) if text else 'pending')


def tracker_csv_text(df: pd.DataFrame) -> str:
    output = io.StringIO()
    df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return output.getvalue()


def to_tracker_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=TRACKER_COLUMNS)
    normalized = normalize_frame(frame).copy()
    if 'pick' in normalized.columns and 'prediction' not in normalized.columns:
        normalized['prediction'] = normalized['pick']
    if 'probability' in normalized.columns and 'model_probability' not in normalized.columns:
        normalized['model_probability'] = normalized['probability']
    if 'result' in normalized.columns and 'result_status' not in normalized.columns:
        normalized['result_status'] = normalized['result']
    if 'created_at' in normalized.columns and 'prediction_timestamp' not in normalized.columns:
        normalized['prediction_timestamp'] = normalized['created_at']
    if 'read' in normalized.columns and 'confidence_tier' not in normalized.columns:
        normalized['confidence_tier'] = normalized['read']
    for column in TRACKER_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ''
    normalized = normalized[TRACKER_COLUMNS].copy()
    normalized['result_status'] = normalized['result_status'].apply(clean_result)
    normalized = normalized[normalized['event'].fillna('').astype(str).str.strip().ne('') & normalized['prediction'].fillna('').astype(str).str.strip().ne('')]
    return normalized.drop_duplicates(subset=['event', 'market_type', 'prediction', 'prediction_timestamp', 'decimal_price'], keep='last').reset_index(drop=True)


def tracker_df() -> pd.DataFrame:
    if 'ara_learning_records' not in st.session_state:
        st.session_state.ara_learning_records = []
    df = pd.DataFrame(st.session_state.ara_learning_records)
    if df.empty:
        return pd.DataFrame(columns=TRACKER_COLUMNS)
    return to_tracker_frame(df)


def set_tracker(df: pd.DataFrame) -> None:
    st.session_state.ara_learning_records = to_tracker_frame(df).to_dict('records')


def merge_into_tracker(new_df: pd.DataFrame) -> int:
    current = tracker_df()
    before = len(current)
    combined = pd.concat([current, to_tracker_frame(new_df)], ignore_index=True)
    cleaned = to_tracker_frame(combined)
    set_tracker(cleaned)
    return max(0, len(cleaned) - before)


def resolved_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {'resolved': 0, 'wins': 0, 'losses': 0, 'hit_rate': None, 'avg_probability': None, 'brier': None}
    statuses = [result_status(row) for row in frame.to_dict(orient='records')]
    wins = statuses.count('win')
    losses = statuses.count('loss')
    resolved = wins + losses
    probs = pd.to_numeric(frame.get('model_probability', pd.Series(dtype=float)), errors='coerce')
    actuals = pd.Series([1 if status == 'win' else 0 if status == 'loss' else None for status in statuses], dtype='float')
    valid = probs.notna() & actuals.notna()
    brier = None if not valid.any() else round(float(((probs[valid] - actuals[valid]) ** 2).mean()), 6)
    return {
        'resolved': int(resolved),
        'wins': int(wins),
        'losses': int(losses),
        'hit_rate': None if resolved == 0 else round(wins / resolved, 6),
        'avg_probability': None if probs.dropna().empty else round(float(probs.dropna().mean()), 6),
        'brier': brier,
    }


def group_learning(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=[column, 'rows', 'wins', 'losses', 'hit_rate'])
    rows: list[dict[str, Any]] = []
    for value, group in frame.groupby(column, dropna=False):
        statuses = [result_status(row) for row in group.to_dict(orient='records')]
        wins = statuses.count('win')
        losses = statuses.count('loss')
        resolved = wins + losses
        rows.append({column: value, 'rows': int(len(group)), 'wins': wins, 'losses': losses, 'resolved': resolved, 'hit_rate': None if resolved == 0 else round(wins / resolved, 6)})
    return pd.DataFrame(rows).sort_values(['resolved', 'rows'], ascending=False)


st.title('Learning Memory Studio')
st.caption('This replaces the old session-only self-learning page. It now acts as a useful workspace for importing picks, marking results, creating learning memory, and running the max intelligence stack.')
st.info('Use this page for quick review and manual result marking. For permanent proof, still use Agent Decision Engine → Odds Lock → Max Agent Intelligence → Proof Readiness.')

latest_predictions = st.session_state.get('ara_latest_predictions', [])
latest_source = st.session_state.get('ara_latest_predictions_source', 'Predictor')
latest_saved_at = st.session_state.get('ara_latest_predictions_saved_at', '')
if latest_predictions:
    st.success(f'Latest predictor scan ready: {len(latest_predictions)} rows from {latest_source} {latest_saved_at}')
    if st.button('Import latest predictor scan', type='primary'):
        added = merge_into_tracker(pd.DataFrame(latest_predictions))
        st.success(f'Imported rows: {added}')
        st.rerun()
else:
    st.caption('No latest predictor scan found. Run Pro Predictor first in this same app session, or upload a CSV below.')

upload_col, tracker_col = st.columns(2)
with upload_col:
    uploaded_files = st.file_uploader('Upload prediction/result CSVs', type=['csv'], accept_multiple_files=True)
with tracker_col:
    previous_tracker = st.file_uploader('Upload previous tracker CSV', type=['csv'], key='previous_tracker_upload')

loaded_rows = 0
if uploaded_files:
    for file in uploaded_files:
        try:
            loaded_rows += merge_into_tracker(pd.read_csv(file))
        except Exception as exc:
            st.warning(f'Could not load {file.name}: {exc}')
if previous_tracker is not None:
    try:
        loaded_rows += merge_into_tracker(pd.read_csv(previous_tracker))
    except Exception as exc:
        st.warning(f'Could not load previous tracker: {exc}')
if loaded_rows:
    st.success(f'Loaded/merged new rows: {loaded_rows}')

with st.expander('Manual record', expanded=False):
    c1, c2, c3 = st.columns(3)
    event = c1.text_input('Event')
    sport = c2.text_input('Sport', 'unknown')
    market_type = c3.text_input('Market type', 'moneyline')
    c4, c5, c6 = st.columns(3)
    prediction = c4.text_input('Prediction')
    probability = c5.number_input('Model probability', min_value=0.0, max_value=1.0, value=0.55, step=0.01)
    decimal_price = c6.number_input('Decimal price', min_value=0.0, max_value=100.0, value=0.0, step=0.01)
    c7, c8, c9 = st.columns(3)
    result = c7.selectbox('Result', ['pending', 'win', 'loss', 'void'])
    event_start = c8.text_input('Event start UTC', '')
    bookmaker = c9.text_input('Bookmaker/source', '')
    if st.button('Add manual record') and event.strip() and prediction.strip():
        merge_into_tracker(pd.DataFrame([{
            'event': event,
            'sport': sport,
            'market_type': market_type,
            'prediction': prediction,
            'model_probability': probability,
            'decimal_price': decimal_price if decimal_price > 0 else '',
            'bookmaker': bookmaker,
            'odds_source': bookmaker,
            'prediction_timestamp': utc_now_iso(),
            'event_start_utc': event_start,
            'result_status': result,
        }]))
        st.rerun()

current = tracker_df()
if current.empty:
    st.warning('No rows loaded yet. Upload a CSV, import the latest predictor scan, or add a manual record.')
    st.stop()

summary = resolved_summary(current)
decisions = build_agent_decisions(current)
decision_summary = agent_decision_summary(current)
plays = playable_candidates(current)
lock_ready = lock_ready_candidates(current)
snapshots = build_api_snapshots(current)
snapshot_summary = snapshot_memory_summary(current)
manifest = export_snapshot_manifest(current)
losses = build_loss_autopsies(current)
loss_summary = autopsy_summary(current)
rules = future_rules(current)
clv = build_clv_intelligence(current)
clv_stats = clv_summary(current)
clv_sport = clv_by_segment(current, 'sport')
walk = walk_forward_validate(current, min_train_rows=5)
walk_stats = walk_forward_summary(current, min_train_rows=5)
sport_decisions = build_sport_specific_decisions(current)
sport_summary = sport_model_summary(current)

cols = st.columns(8)
cols[0].metric('Rows', len(current))
cols[1].metric('Resolved', summary['resolved'])
cols[2].metric('Wins', summary['wins'])
cols[3].metric('Losses', summary['losses'])
cols[4].metric('Hit Rate', 'N/A' if summary['hit_rate'] is None else f"{summary['hit_rate']:.1%}")
cols[5].metric('Brier', 'N/A' if summary['brier'] is None else summary['brier'])
cols[6].metric('Playable', decision_summary['play_strong'] + decision_summary['play_small'])
cols[7].metric('Lock Ready', decision_summary['lock_ready_candidates'])

tab_editor, tab_decisions, tab_memory, tab_losses, tab_clv, tab_walk, tab_sport, tab_exports = st.tabs([
    'Edit Results',
    'Agent Decisions',
    'Snapshot Memory',
    'Loss Autopsy',
    'CLV',
    'Walk-Forward',
    'Sport Models',
    'Exports',
])

with tab_editor:
    st.subheader('Editable tracker')
    editable = st.data_editor(
        current,
        use_container_width=True,
        hide_index=True,
        num_rows='dynamic',
        column_config={
            'result_status': st.column_config.SelectboxColumn('Result', options=['pending', 'win', 'loss', 'void']),
            'model_probability': st.column_config.NumberColumn('Model probability', min_value=0.0, max_value=1.0, step=0.01),
            'decimal_price': st.column_config.NumberColumn('Decimal price', min_value=0.0, step=0.01),
            'closing_decimal_price': st.column_config.NumberColumn('Closing decimal price', min_value=0.0, step=0.01),
            'stake_units': st.column_config.NumberColumn('Stake units', min_value=0.0, step=0.1),
            'profit_units': st.column_config.NumberColumn('Profit units', step=0.1),
        },
        key='learning_memory_studio_editor',
    )
    set_tracker(editable)
    st.subheader('Simple learning summaries')
    s1, s2, s3 = st.tabs(['By Sport', 'By Market', 'By Confidence'])
    with s1:
        st.dataframe(group_learning(tracker_df(), 'sport'), use_container_width=True, hide_index=True)
    with s2:
        st.dataframe(group_learning(tracker_df(), 'market_type'), use_container_width=True, hide_index=True)
    with s3:
        st.dataframe(group_learning(tracker_df(), 'confidence_tier'), use_container_width=True, hide_index=True)

with tab_decisions:
    st.json(decision_summary)
    st.dataframe(decisions.head(500), use_container_width=True, hide_index=True)
    st.subheader('Playable candidates')
    st.dataframe(plays.head(300), use_container_width=True, hide_index=True)
    st.subheader('Lock-ready candidates')
    st.dataframe(lock_ready.head(300), use_container_width=True, hide_index=True)

with tab_memory:
    st.json(snapshot_summary)
    st.dataframe(snapshots.head(300), use_container_width=True, hide_index=True)

with tab_losses:
    st.json(loss_summary)
    st.dataframe(losses.head(300), use_container_width=True, hide_index=True)
    st.subheader('Future rules')
    st.dataframe(rules, use_container_width=True, hide_index=True)

with tab_clv:
    st.json(clv_stats)
    st.dataframe(clv.head(300), use_container_width=True, hide_index=True)
    st.subheader('CLV by sport')
    st.dataframe(clv_sport, use_container_width=True, hide_index=True)

with tab_walk:
    st.json(walk_stats)
    st.dataframe(walk.head(300), use_container_width=True, hide_index=True)

with tab_sport:
    st.dataframe(sport_summary, use_container_width=True, hide_index=True)
    st.dataframe(sport_decisions.head(300), use_container_width=True, hide_index=True)

with tab_exports:
    st.download_button('Download updated tracker CSV', tracker_csv_text(tracker_df()), file_name='learning_memory_tracker.csv', mime='text/csv')
    st.download_button('Download agent decisions CSV', decisions.to_csv(index=False), file_name='learning_agent_decisions.csv', mime='text/csv')
    st.download_button('Download API snapshot memory CSV', snapshots.to_csv(index=False), file_name='learning_api_snapshot_memory.csv', mime='text/csv')
    st.download_button('Download API snapshot manifest JSON', __import__('json').dumps(manifest, indent=2, default=str), file_name='learning_api_snapshot_manifest.json', mime='application/json')
    st.download_button('Download loss autopsies CSV', losses.to_csv(index=False), file_name='learning_loss_autopsies.csv', mime='text/csv')
    st.download_button('Download future rules CSV', rules.to_csv(index=False), file_name='learning_future_rules.csv', mime='text/csv')
    st.download_button('Download CLV intelligence CSV', clv.to_csv(index=False), file_name='learning_clv_intelligence.csv', mime='text/csv')
    st.download_button('Download walk-forward CSV', walk.to_csv(index=False), file_name='learning_walk_forward.csv', mime='text/csv')
    st.download_button('Download sport-specific decisions CSV', sport_decisions.to_csv(index=False), file_name='learning_sport_decisions.csv', mime='text/csv')

if st.button('Clear session tracker'):
    st.session_state.ara_learning_records = []
    st.rerun()

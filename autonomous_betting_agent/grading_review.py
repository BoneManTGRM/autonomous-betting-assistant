from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


def _safe(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value).strip()


def _first(row: Mapping[str, Any], *names: str) -> str:
    normalized = {str(key).lower().replace(' ', '_').replace('-', '_'): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower().replace(' ', '_').replace('-', '_'))
        if _safe(value):
            return _safe(value)
    return ''


def review_status(row: Mapping[str, Any]) -> tuple[str, str]:
    raw_status = _first(row, 'result_status', 'clean_grading_status', 'status', 'result', 'outcome', 'win_loss').lower()
    event = _first(row, 'event', 'game', 'match')
    prediction = _first(row, 'prediction', 'pick', 'selection')
    final_score = _first(row, 'final_score', 'score', 'actual_score')
    winner = _first(row, 'winner', 'actual_winner', 'final_winner')
    duplicate = _first(row, 'duplicate', 'is_duplicate').lower() in {'true', 'yes', '1', 'duplicate'}

    if duplicate:
        return 'duplicate', 'Duplicate row; exclude from official performance.'
    if raw_status in {'void', 'cancelled', 'canceled', 'postponed', 'abandoned'}:
        return 'void', 'Event was void/canceled/postponed/abandoned.'
    if raw_status in {'win', 'won', 'loss', 'lost'}:
        return 'graded_clean', 'Already has clean win/loss result.'
    if raw_status in {'review_needed', 'review needed', 'unclear', 'format_mismatch'}:
        return 'review_needed', 'Existing status says this row needs manual review.'
    if not event or not prediction:
        return 'review_needed', 'Missing event or prediction.'
    if winner or final_score:
        return 'ready_to_grade', 'Final score/winner appears present; row can be graded.'
    if raw_status in {'pending', 'live', 'scheduled', 'unknown', ''}:
        return 'pending', 'No confirmed final result yet.'
    return 'review_needed', f'Unrecognized result status: {raw_status}'


def build_review_queue(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=['review_status', 'review_reason'])
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient='records'):
        status, reason = review_status(raw)
        item = dict(raw)
        item['review_status'] = status
        item['review_reason'] = reason
        rows.append(item)
    out = pd.DataFrame(rows)
    order = {'ready_to_grade': 0, 'review_needed': 1, 'pending': 2, 'void': 3, 'duplicate': 4, 'graded_clean': 5}
    out['_review_order'] = out['review_status'].map(order).fillna(99)
    return out.sort_values(['_review_order']).drop(columns=['_review_order'])


def review_summary(frame: pd.DataFrame) -> pd.DataFrame:
    queue = build_review_queue(frame)
    if queue.empty or 'review_status' not in queue.columns:
        return pd.DataFrame(columns=['review_status', 'count'])
    return queue.groupby('review_status').size().reset_index(name='count').sort_values('count', ascending=False)

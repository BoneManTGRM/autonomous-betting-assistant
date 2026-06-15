from __future__ import annotations

from typing import Any

import pandas as pd

from .row_normalizer import normalize_frame, result_status, safe_text

TERMINAL_RESULTS = {'win', 'loss', 'void'}
PENDING_RESULTS = {'pending', 'live', 'scheduled', 'unknown', ''}


def grade_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_frame(pd.DataFrame([row])).iloc[0].to_dict()
    status = result_status(normalized)
    prediction = safe_text(normalized.get('prediction')).lower()
    winner = safe_text(normalized.get('winner')).lower()
    final_score = safe_text(normalized.get('final_score'))
    source_url = safe_text(normalized.get('result_source_url'))

    if status in TERMINAL_RESULTS:
        return {'graded_result': status, 'grade_status': 'graded_clean', 'grade_reason': f'Existing terminal result: {status}.', 'needs_review': False}
    if prediction and winner:
        outcome = 'win' if prediction == winner else 'loss'
        return {'graded_result': outcome, 'grade_status': 'graded_from_winner', 'grade_reason': 'Prediction compared to winner field.', 'needs_review': False}
    if final_score and not winner:
        return {'graded_result': 'pending', 'grade_status': 'review_needed', 'grade_reason': 'Final score present but winner missing.', 'needs_review': True}
    if status in PENDING_RESULTS:
        return {'graded_result': 'pending', 'grade_status': 'pending', 'grade_reason': 'No terminal result detected yet.', 'needs_review': False}
    return {'graded_result': 'pending', 'grade_status': 'review_needed', 'grade_reason': f'Unrecognized result status: {status}.', 'needs_review': True}


def grade_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    rows = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(grade_row(row))
        rows.append(item)
    return pd.DataFrame(rows)


def grade_summary(frame: pd.DataFrame) -> dict[str, int]:
    graded = grade_frame(frame)
    if graded.empty:
        return {'rows': 0, 'wins': 0, 'losses': 0, 'voids': 0, 'pending': 0, 'review_needed': 0}
    result = graded['graded_result'].fillna('').astype(str)
    status = graded['grade_status'].fillna('').astype(str)
    return {
        'rows': int(len(graded)),
        'wins': int(result.eq('win').sum()),
        'losses': int(result.eq('loss').sum()),
        'voids': int(result.eq('void').sum()),
        'pending': int(result.eq('pending').sum()),
        'review_needed': int(status.eq('review_needed').sum()),
    }

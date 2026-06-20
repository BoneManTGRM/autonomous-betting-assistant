from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


def _text(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {'nan', 'none', 'null', 'na', 'n/a'}:
        return ''
    return text


def _event_key(row: Mapping[str, Any]) -> str:
    return ' '.join(_text(row.get('event')).lower().split())


def _has_detail(row: Mapping[str, Any]) -> bool:
    fields = (
        'model_probability', 'model_probability_clean', 'market_probability',
        'market_implied_probability', 'decimal_price', 'odds_at_pick', 'best_price',
        'average_price', 'worst_price', 'bookmaker', 'bookmaker_count', 'books',
        'agent_score', 'signal_strength_score', 'api_coverage_score',
    )
    return any(_text(row.get(field)) for field in fields)


def remove_lower_detail_event_overlaps(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or 'event' not in frame.columns:
        return frame.copy() if frame is not None else pd.DataFrame()
    rows = [dict(row) for row in frame.to_dict(orient='records')]
    detailed_events = {_event_key(row) for row in rows if _event_key(row) and _has_detail(row)}
    if not detailed_events:
        return frame.copy()
    kept = [row for row in rows if _event_key(row) not in detailed_events or _has_detail(row)]
    return pd.DataFrame(kept, columns=frame.columns)

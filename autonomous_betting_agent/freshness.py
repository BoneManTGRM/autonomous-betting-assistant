from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

FRESHNESS_SCHEMA_VERSION = 'freshness-v1'
DEFAULT_LIMITS_HOURS = {
    'odds': 2,
    'prediction': 24,
    'results': 12,
    'memory': 168,
}


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


def parse_datetime(value: Any) -> datetime | None:
    text = _safe(value)
    if not text:
        return None
    text = text.replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(value: Any, *, now: datetime | None = None) -> float | None:
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - parsed).total_seconds() / 3600.0)


def freshness_check(name: str, timestamp: Any, limit_hours: float, *, now: datetime | None = None) -> dict[str, Any]:
    age = age_hours(timestamp, now=now)
    if age is None:
        return {'check': name, 'status': 'missing', 'age_hours': None, 'limit_hours': limit_hours, 'message': f'{name} timestamp missing.'}
    if age <= limit_hours:
        return {'check': name, 'status': 'fresh', 'age_hours': round(age, 2), 'limit_hours': limit_hours, 'message': f'{name} is fresh.'}
    return {'check': name, 'status': 'stale', 'age_hours': round(age, 2), 'limit_hours': limit_hours, 'message': f'{name} is stale: {age:.1f} hours old.'}


def build_freshness_frame(frame: pd.DataFrame, *, memory_bank: Mapping[str, Any] | None = None, now: datetime | None = None) -> pd.DataFrame:
    now = now or datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    if frame is not None and not frame.empty:
        for idx, raw in enumerate(frame.to_dict(orient='records'), start=1):
            event = _first(raw, 'event', 'game', 'match') or f'row {idx}'
            odds_ts = _first(raw, 'odds_timestamp', 'price_timestamp', 'last_odds_update', 'last_update')
            pred_ts = _first(raw, 'prediction_timestamp', 'locked_at_utc', 'created_at', 'scan_timestamp')
            result_ts = _first(raw, 'result_timestamp', 'final_timestamp', 'graded_at_utc')
            for check in [
                freshness_check('odds', odds_ts, DEFAULT_LIMITS_HOURS['odds'], now=now),
                freshness_check('prediction', pred_ts, DEFAULT_LIMITS_HOURS['prediction'], now=now),
            ]:
                check['event'] = event
                rows.append(check)
            if result_ts:
                result_check = freshness_check('results', result_ts, DEFAULT_LIMITS_HOURS['results'], now=now)
                result_check['event'] = event
                rows.append(result_check)
    if memory_bank is not None:
        memory_ts = memory_bank.get('trained_at_utc') or memory_bank.get('global_calibrator', {}).get('trained_at_utc') if isinstance(memory_bank, dict) else ''
        check = freshness_check('memory', memory_ts, DEFAULT_LIMITS_HOURS['memory'], now=now)
        check['event'] = 'learning_memory'
        rows.append(check)
    return pd.DataFrame(rows)


def freshness_summary(freshness: pd.DataFrame) -> dict[str, int]:
    if freshness is None or freshness.empty:
        return {'checks': 0, 'fresh': 0, 'stale': 0, 'missing': 0}
    status = freshness.get('status', pd.Series(dtype=str)).fillna('').astype(str)
    return {
        'checks': int(len(freshness)),
        'fresh': int(status.eq('fresh').sum()),
        'stale': int(status.eq('stale').sum()),
        'missing': int(status.eq('missing').sum()),
    }


def freshness_score(freshness: pd.DataFrame) -> int:
    summary = freshness_summary(freshness)
    if summary['checks'] == 0:
        return 0
    score = 100
    score -= summary['stale'] * 12
    score -= summary['missing'] * 8
    return max(0, min(100, score))

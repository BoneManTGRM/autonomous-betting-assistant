from __future__ import annotations

from typing import Any, Iterable, Mapping

import pandas as pd

from .audit import parse_float


def _safe(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value).strip()


def _first(row: Mapping[str, Any], *names: str) -> Any:
    normalized = {str(key).lower().replace(' ', '_').replace('-', '_'): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower().replace(' ', '_').replace('-', '_'))
        if _safe(value):
            return value
    return ''


def _probability(value: Any) -> float | None:
    number = parse_float(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    return number if 0.0 < number < 1.0 else None


def _boolish(value: Any) -> bool:
    return str(value or '').strip().lower() in {'true', 'yes', '1', 'positive_clv', 'official_locked'}


def _memory_support(row: Mapping[str, Any], memory_patterns: Iterable[Mapping[str, Any]] | None = None) -> tuple[int, str]:
    if not memory_patterns:
        return 0, 'No memory pattern support loaded.'
    sport = _safe(_first(row, 'sport', 'league')).lower()
    confidence = _safe(_first(row, 'confidence_tier', 'confidence')).lower()
    best_score = 0
    best_reason = 'No matching memory support.'
    for pattern in memory_patterns:
        area = _safe(pattern.get('area')).lower()
        action = _safe(pattern.get('action') or pattern.get('recommended_action')).lower()
        records = int(parse_float(pattern.get('records')) or 0)
        reliability = parse_float(pattern.get('reliability')) or 0.0
        if records < 3:
            continue
        matched = (sport and sport in area) or (confidence and confidence in area) or 'probability bucket' in area
        if not matched:
            continue
        if action == 'raise_trust':
            score = min(10, int(round(4 + reliability * 8)))
            reason = f'Memory supports this area ({records} records).'
        elif action == 'lower_trust':
            score = -min(12, int(round(4 + reliability * 10)))
            reason = f'Memory warns against this area ({records} records).'
        else:
            score = min(4, int(round(reliability * 5)))
            reason = f'Memory says watch this area ({records} records).'
        if abs(score) > abs(best_score):
            best_score = score
            best_reason = reason
    return best_score, best_reason


def score_pick(row: Mapping[str, Any], memory_patterns: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    probability = _probability(_first(row, 'model_probability', 'final_probability', 'final_probability_value', 'probability'))
    price = parse_float(_first(row, 'decimal_price', 'best_price', 'odds'))
    ev = parse_float(_first(row, 'estimated_ev_decimal', 'computed_ev_decimal', 'estimated_ev_value'))
    api_coverage = parse_float(_first(row, 'api_coverage_score', 'api_coverage'))
    if api_coverage is not None and api_coverage > 1.0:
        api_coverage /= 100.0
    books = parse_float(_first(row, 'books', 'bookmaker_count', 'source_count', 'bookmakers'))
    lock_status = _safe(_first(row, 'lock_status')).lower()
    review_status = _safe(_first(row, 'review_status', 'clean_grading_status')).lower()
    decision = _safe(_first(row, 'decision')).lower()
    confidence_tier = _safe(_first(row, 'confidence_tier')).lower()

    if probability is not None:
        probability_points = 20 if probability >= 0.70 else 16 if probability >= 0.62 else 11 if probability >= 0.55 else 5
        score += probability_points
        reasons.append(f'Model probability contributes {probability_points} points.')
    else:
        reasons.append('Missing model probability.')

    if price is not None and price > 1.0:
        score += 15
        reasons.append('Usable decimal odds present.')
    else:
        reasons.append('Missing usable odds.')

    if ev is not None:
        ev_points = 15 if ev >= 0.05 else 10 if ev > 0 else 3
        score += ev_points
        reasons.append(f'EV contributes {ev_points} points.')
    else:
        reasons.append('EV unavailable.')

    if api_coverage is not None:
        points = int(round(max(0.0, min(1.0, api_coverage)) * 10))
        score += points
        reasons.append(f'API coverage contributes {points} points.')
    else:
        reasons.append('API coverage unavailable.')

    if books is not None:
        points = 10 if books >= 6 else 7 if books >= 3 else 4 if books >= 1 else 0
        score += points
        reasons.append(f'Book coverage contributes {points} points.')
    else:
        reasons.append('Book count unavailable.')

    if lock_status == 'official_locked':
        score += 15
        reasons.append('Official odds lock present.')
    elif not lock_status:
        score += 4
        reasons.append('No odds lock status found.')
    else:
        score -= 12
        reasons.append('Not official locked.')

    if _boolish(_first(row, 'clv_positive')):
        score += 8
        reasons.append('Positive CLV detected.')

    memory_points, memory_reason = _memory_support(row, memory_patterns)
    score += memory_points
    reasons.append(memory_reason)

    if 'a+ high' in confidence_tier or 'a strong' in confidence_tier:
        score += 8
        reasons.append('Strong confidence tier.')
    elif 'watch' in confidence_tier or 'no bet' in confidence_tier:
        score -= 10
        reasons.append('Watch/no-bet tier penalty.')

    if 'watch' in decision or 'skip' in decision or 'no_bet' in decision:
        score -= 12
        reasons.append('Decision is not actionable.')

    if review_status in {'review_needed', 'review needed'}:
        score -= 20
        reasons.append('Manual review needed.')

    score = int(max(0, min(100, round(score))))
    if score >= 90:
        grade = 'Elite'
        action = 'A+ candidate'
    elif score >= 80:
        grade = 'Strong'
        action = 'A candidate'
    elif score >= 65:
        grade = 'Playable'
        action = 'B lean'
    elif score >= 50:
        grade = 'Watch'
        action = 'watch only'
    else:
        grade = 'No Bet'
        action = 'no bet'
    return {'pick_quality_score': score, 'pick_quality_grade': grade, 'quality_action': action, 'quality_reasons': ' '.join(reasons)}


def build_pick_quality_frame(frame: pd.DataFrame, memory_patterns: Iterable[Mapping[str, Any]] | None = None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient='records'):
        item = dict(raw)
        item.update(score_pick(raw, memory_patterns))
        rows.append(item)
    return pd.DataFrame(rows).sort_values('pick_quality_score', ascending=False)


def pick_quality_summary(frame: pd.DataFrame) -> dict[str, int]:
    scored = build_pick_quality_frame(frame)
    if scored.empty:
        return {'rows': 0, 'elite': 0, 'strong': 0, 'playable': 0, 'watch': 0, 'no_bet': 0}
    grades = scored['pick_quality_grade'].value_counts().to_dict()
    return {
        'rows': int(len(scored)),
        'elite': int(grades.get('Elite', 0)),
        'strong': int(grades.get('Strong', 0)),
        'playable': int(grades.get('Playable', 0)),
        'watch': int(grades.get('Watch', 0)),
        'no_bet': int(grades.get('No Bet', 0)),
    }

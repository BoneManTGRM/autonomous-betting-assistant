from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Mapping

import pandas as pd

from .commercial_platform_tools import apply_result_updates, filter_locked_proof_rows, load_persistent_ledger, save_persistent_ledger
from .row_normalizer import safe_text


def _clean(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').replace('@', ' at ').split())


def _similarity(left: Any, right: Any) -> float:
    a, b = _clean(left), _clean(right)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _date_prefix(value: Any) -> str:
    text = safe_text(value)
    return text[:10] if len(text) >= 10 else ''


def normalize_result_feed(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    if raw is None or raw.empty:
        return pd.DataFrame()
    rows = []
    for row in raw.to_dict(orient='records'):
        item = dict(row)
        winner = safe_text(item.get('winner') or item.get('actual_winner') or item.get('final_winner'))
        home = safe_text(item.get('home_team'))
        away = safe_text(item.get('away_team'))
        home_score = _score_value(item.get('home_score'))
        away_score = _score_value(item.get('away_score'))
        if not winner and home and away and home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = home
            elif away_score > home_score:
                winner = away
            else:
                item['result_status'] = 'void'
        if winner:
            item['winner'] = winner
        if home and away and not safe_text(item.get('event')):
            item['event'] = f'{away} at {home}'
        if home_score is not None and away_score is not None and not safe_text(item.get('final_score')):
            item['final_score'] = f'{home} {home_score} - {away_score} {away}'
        rows.append(item)
    return pd.DataFrame(rows)


def _score_value(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == '':
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def odds_scores_to_result_frame(payload: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for event in payload or []:
        completed = bool(event.get('completed', False))
        if not completed:
            continue
        scores = event.get('scores') or []
        score_map: dict[str, int] = {}
        for score in scores:
            name = safe_text(score.get('name'))
            raw_score = _score_value(score.get('score'))
            if name and raw_score is not None:
                score_map[name] = raw_score
        home = safe_text(event.get('home_team'))
        away = safe_text(event.get('away_team'))
        home_score = score_map.get(home)
        away_score = score_map.get(away)
        winner = ''
        status = 'pending'
        if home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = home
                status = 'win_or_loss_by_pick'
            elif away_score > home_score:
                winner = away
                status = 'win_or_loss_by_pick'
            else:
                status = 'void'
        rows.append({
            'event': f'{away} at {home}' if away and home else safe_text(event.get('id')),
            'sport_key': safe_text(event.get('sport_key')),
            'sport': safe_text(event.get('sport_title') or event.get('sport_key')),
            'event_start_utc': safe_text(event.get('commence_time')),
            'home_team': home,
            'away_team': away,
            'home_score': home_score,
            'away_score': away_score,
            'winner': winner,
            'result_status': status,
            'final_score': '' if home_score is None or away_score is None else f'{away} {away_score} - {home_score} {home}',
        })
    return pd.DataFrame(rows)


def fuzzy_match_results(ledger: pd.DataFrame | list[dict[str, Any]], results: pd.DataFrame | list[dict[str, Any]], *, threshold: float = 0.86) -> pd.DataFrame:
    locked = filter_locked_proof_rows(ledger)
    result_frame = normalize_result_feed(results)
    if locked.empty or result_frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for lrow in locked.to_dict(orient='records'):
        best: dict[str, Any] | None = None
        best_score = 0.0
        for rrow in result_frame.to_dict(orient='records'):
            event_score = _similarity(lrow.get('event'), rrow.get('event'))
            sport_score = max(_similarity(lrow.get('sport'), rrow.get('sport')), _similarity(lrow.get('sport_key'), rrow.get('sport_key')))
            date_match = bool(_date_prefix(lrow.get('event_start_utc')) and _date_prefix(lrow.get('event_start_utc')) == _date_prefix(rrow.get('event_start_utc')))
            pick_score = max(_similarity(lrow.get('prediction'), rrow.get('winner')), _similarity(lrow.get('prediction'), rrow.get('home_team')), _similarity(lrow.get('prediction'), rrow.get('away_team')))
            score = event_score * 0.55 + sport_score * 0.15 + (0.15 if date_match else 0.0) + pick_score * 0.15
            if score > best_score:
                best_score = score
                best = rrow
        status = 'matched' if best is not None and best_score >= threshold else 'needs_review'
        rows.append({
            'proof_id': safe_text(lrow.get('proof_id')),
            'ledger_event': safe_text(lrow.get('event')),
            'ledger_prediction': safe_text(lrow.get('prediction')),
            'matched_event': safe_text((best or {}).get('event')),
            'matched_winner': safe_text((best or {}).get('winner')),
            'matched_final_score': safe_text((best or {}).get('final_score')),
            'match_confidence': round(best_score, 4),
            'match_status': status,
        })
    return pd.DataFrame(rows)


def result_match_summary(matches: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(matches) if isinstance(matches, list) else matches
    if frame is None or frame.empty:
        return {'rows': 0, 'matched': 0, 'needs_review': 0, 'avg_confidence': None}
    status = frame.get('match_status', pd.Series(dtype=str)).astype(str)
    conf = pd.to_numeric(frame.get('match_confidence', pd.Series(dtype=float)), errors='coerce')
    return {
        'rows': int(len(frame)),
        'matched': int(status.eq('matched').sum()),
        'needs_review': int(status.eq('needs_review').sum()),
        'avg_confidence': None if conf.dropna().empty else round(float(conf.mean()), 4),
    }


def grade_persistent_ledger_with_results(results: pd.DataFrame | list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    ledger = load_persistent_ledger()
    result_frame = normalize_result_feed(results)
    matches = fuzzy_match_results(ledger, result_frame)
    updated, stats = apply_result_updates(ledger, result_frame)
    stats['match_summary'] = result_match_summary(matches)
    if not updated.empty:
        save_persistent_ledger(updated)
    return updated, stats


def grading_summary(ledger: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    locked = filter_locked_proof_rows(ledger)
    if locked.empty:
        return {'locked_rows': 0, 'resolved_rows': 0, 'pending_rows': 0, 'graded_percent': 0.0}
    status = locked.get('result_status', pd.Series(dtype=str)).astype(str).str.lower()
    resolved = int(status.isin(['win', 'loss', 'void']).sum())
    pending = int(len(locked) - resolved)
    return {'locked_rows': int(len(locked)), 'resolved_rows': resolved, 'pending_rows': pending, 'graded_percent': round(resolved / len(locked), 6)}


def result_upload_template() -> pd.DataFrame:
    return pd.DataFrame([
        {
            'proof_id': 'OLP-EXAMPLE1234',
            'event': 'Away Team at Home Team',
            'prediction': 'Home Team',
            'market_type': 'h2h',
            'event_start_utc': '2099-01-01T00:00:00Z',
            'winner': 'Home Team',
            'final_score': 'Away Team 1 - 2 Home Team',
            'result_status': 'win',
            'closing_decimal_price': 1.91,
        }
    ])

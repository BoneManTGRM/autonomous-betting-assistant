from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Mapping

import pandas as pd

from .commercial_platform_tools import filter_locked_proof_rows, load_persistent_ledger, save_persistent_ledger
from .row_normalizer import result_status, safe_text

RESOLVED = {'win', 'loss', 'void'}
PENDING = {'', 'pending', 'unknown', 'scheduled', 'live', 'needs_review'}


def clean(value: Any) -> str:
    return ' '.join(safe_text(value).lower().replace('-', ' ').replace('_', ' ').replace('@', ' at ').split())


def sim(a: Any, b: Any) -> float:
    left, right = clean(a), clean(b)
    if not left or not right:
        return 0.0
    if left == right or left in right or right in left:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def day(value: Any) -> str:
    text = safe_text(value)
    return text[:10] if len(text) >= 10 else ''


def score_value(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == '':
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def line_value(row: Mapping[str, Any]) -> float | None:
    for key in ('line_point', 'point', 'spread', 'total'):
        parsed = number(row.get(key))
        if parsed is not None:
            return parsed
    found = re.findall(r'[+-]?\d+(?:\.\d+)?', safe_text(row.get('prediction')))
    return float(found[-1]) if found else None


def market_kind(row: Mapping[str, Any]) -> str:
    text = clean(row.get('market_type') or row.get('market') or row.get('prediction'))
    pick = clean(row.get('prediction'))
    if 'over' in pick or 'under' in pick or 'total' in text:
        return 'total'
    if 'spread' in text or 'handicap' in text or re.search(r'(^|\s)[+-]\d+(?:\.\d+)?(\s|$)', safe_text(row.get('prediction'))):
        return 'spread'
    return 'h2h'


def normalize_results(results: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(results) if isinstance(results, list) else results
    if raw is None or raw.empty:
        return pd.DataFrame()
    rows = []
    for row in raw.to_dict(orient='records'):
        item = dict(row)
        home = safe_text(item.get('home_team'))
        away = safe_text(item.get('away_team'))
        home_score = score_value(item.get('home_score'))
        away_score = score_value(item.get('away_score'))
        winner = safe_text(item.get('winner') or item.get('actual_winner') or item.get('final_winner'))
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
        if home_score is not None:
            item['home_score'] = home_score
        if away_score is not None:
            item['away_score'] = away_score
        if home_score is not None and away_score is not None and not safe_text(item.get('final_score')):
            item['final_score'] = f'{away} {away_score} - {home_score} {home}'
        rows.append(item)
    return pd.DataFrame(rows)


def odds_scores_to_result_frame_v2(payload: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for event in payload or []:
        if not bool(event.get('completed', False)):
            continue
        score_map = {}
        for score in event.get('scores') or []:
            name = safe_text(score.get('name'))
            value = score_value(score.get('score'))
            if name and value is not None:
                score_map[name] = value
        home = safe_text(event.get('home_team'))
        away = safe_text(event.get('away_team'))
        home_score = score_map.get(home)
        away_score = score_map.get(away)
        winner = ''
        status = 'pending'
        if home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = home
                status = 'final'
            elif away_score > home_score:
                winner = away
                status = 'final'
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


def match_score(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> float:
    event_score = sim(ledger_row.get('event'), result_row.get('event'))
    sport_score = max(sim(ledger_row.get('sport'), result_row.get('sport')), sim(ledger_row.get('sport_key'), result_row.get('sport_key')))
    date_score = 1.0 if day(ledger_row.get('event_start_utc')) and day(ledger_row.get('event_start_utc')) == day(result_row.get('event_start_utc')) else 0.0
    pick_score = max(sim(ledger_row.get('prediction'), result_row.get('winner')), sim(ledger_row.get('prediction'), result_row.get('home_team')), sim(ledger_row.get('prediction'), result_row.get('away_team')))
    return event_score * 0.55 + sport_score * 0.15 + date_score * 0.15 + pick_score * 0.15


def side_scores(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> tuple[float, float] | None:
    home = safe_text(result_row.get('home_team'))
    away = safe_text(result_row.get('away_team'))
    hs = score_value(result_row.get('home_score'))
    aw = score_value(result_row.get('away_score'))
    if not home or not away or hs is None or aw is None:
        return None
    pick = clean(ledger_row.get('prediction'))
    if clean(home) in pick:
        return float(hs), float(aw)
    if clean(away) in pick:
        return float(aw), float(hs)
    return None


def grade_pick(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> str:
    status = result_status(result_row)
    if status == 'void':
        return 'void'
    kind = market_kind(ledger_row)
    hs = score_value(result_row.get('home_score'))
    aw = score_value(result_row.get('away_score'))
    if kind == 'total':
        line = line_value(ledger_row)
        pick = clean(ledger_row.get('prediction'))
        if hs is None or aw is None or line is None:
            return 'pending'
        total = hs + aw
        if abs(total - line) < 1e-9:
            return 'void'
        if 'over' in pick:
            return 'win' if total > line else 'loss'
        if 'under' in pick:
            return 'win' if total < line else 'loss'
        return 'pending'
    if kind == 'spread':
        line = line_value(ledger_row)
        scores = side_scores(ledger_row, result_row)
        if line is None or scores is None:
            return 'pending'
        selected, opponent = scores
        adjusted = selected + line - opponent
        if abs(adjusted) < 1e-9:
            return 'void'
        return 'win' if adjusted > 0 else 'loss'
    winner = safe_text(result_row.get('winner') or result_row.get('actual_winner') or result_row.get('final_winner'))
    if winner:
        return 'win' if clean(winner) in clean(ledger_row.get('prediction')) or clean(ledger_row.get('prediction')) in clean(winner) else 'loss'
    if hs is not None and aw is not None and hs == aw:
        return 'void'
    return 'pending'


def apply_fuzzy_updates(ledger: pd.DataFrame | list[dict[str, Any]], results: pd.DataFrame | list[dict[str, Any]], *, threshold: float = 0.82, regrade_resolved: bool = False) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = filter_locked_proof_rows(ledger)
    result_frame = normalize_results(results)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'matched_rows': 0, 'unmatched_pending_rows': 0, 'reason': 'empty_ledger'}
    if result_frame.empty:
        return locked, {'updated_rows': 0, 'matched_rows': 0, 'unmatched_pending_rows': 0, 'reason': 'empty_results'}
    result_rows = result_frame.to_dict(orient='records')
    rows = []
    updated = matched = unmatched = skipped_resolved = 0
    for lrow in locked.to_dict(orient='records'):
        item = dict(lrow)
        current = safe_text(item.get('result_status')).lower()
        if current in RESOLVED and not regrade_resolved:
            item['grading_match_status'] = 'skipped_resolved'
            skipped_resolved += 1
            rows.append(item)
            continue
        best = None
        best_score = 0.0
        proof_id = safe_text(item.get('proof_id'))
        if proof_id:
            for rrow in result_rows:
                if safe_text(rrow.get('proof_id')) == proof_id:
                    best = rrow
                    best_score = 1.0
                    break
        if best is None:
            for rrow in result_rows:
                score = match_score(item, rrow)
                if score > best_score:
                    best_score = score
                    best = rrow
        if best is None or best_score < threshold:
            item['grading_match_status'] = 'no_match'
            item['grading_match_confidence'] = round(best_score, 4)
            unmatched += 1
            rows.append(item)
            continue
        matched += 1
        grade = grade_pick(item, best)
        item['grading_match_status'] = 'matched'
        item['grading_match_confidence'] = round(best_score, 4)
        item['matched_result_event'] = safe_text(best.get('event'))
        if grade in RESOLVED:
            item['result_status'] = grade
            item['winner'] = safe_text(best.get('winner') or item.get('winner'))
            item['final_score'] = safe_text(best.get('final_score') or item.get('final_score'))
            item['graded_at_utc'] = pd.Timestamp.utcnow().isoformat()
            updated += 1
        rows.append(item)
    out = filter_locked_proof_rows(pd.DataFrame(rows))
    return out, {'updated_rows': updated, 'matched_rows': matched, 'skipped_resolved': skipped_resolved, 'unmatched_pending_rows': unmatched, 'result_rows': int(len(result_frame)), 'threshold': threshold}


def grade_persistent_with_fuzzy(results: pd.DataFrame | list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    ledger = load_persistent_ledger()
    updated, stats = apply_fuzzy_updates(ledger, results)
    if not updated.empty:
        save_persistent_ledger(updated)
    return updated, stats

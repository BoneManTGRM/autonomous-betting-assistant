from __future__ import annotations

import os
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from .auto_learning_cycle import run_auto_learning_cycle
from .auto_result_grading_tools import odds_scores_to_result_frame
from .commercial_platform_tools import filter_locked_proof_rows, load_persistent_ledger, save_persistent_ledger
from .live_odds import _get_json, validate_api_key
from .row_normalizer import safe_text

RESOLVED_STATUSES = {'win', 'loss', 'void', 'push', 'cancelled', 'canceled'}


def _secret(*names: str) -> str:
    try:
        import streamlit as st
        for name in names:
            value = str(st.secrets.get(name, '')).strip()
            if value:
                return value
    except Exception:
        pass
    for name in names:
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def _api_key(override: str = '') -> str:
    key = str(override or '').strip() or _secret('THE_ODDS_API_KEY', 'ODDS_API_KEY')
    return validate_api_key(key)


def _clean(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').replace('@', ' at ').split())


def _sim(left: Any, right: Any) -> float:
    a, b = _clean(left), _clean(right)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _date_prefix(value: Any) -> str:
    text = safe_text(value)
    return text[:10] if len(text) >= 10 else ''


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _score(row: dict[str, Any], team: str) -> float | None:
    if _sim(team, row.get('home_team')) >= 0.90:
        return _float(row.get('home_score'))
    if _sim(team, row.get('away_team')) >= 0.90:
        return _float(row.get('away_score'))
    return None


def _winner(home: str, away: str, home_score: float | None, away_score: float | None) -> str:
    if home_score is None or away_score is None:
        return ''
    if home_score > away_score:
        return home
    if away_score > home_score:
        return away
    return ''


def _selected_team(prediction: str, home: str, away: str) -> str:
    home_score = _sim(prediction, home)
    away_score = _sim(prediction, away)
    if home_score >= away_score and home_score >= 0.45:
        return home
    if away_score > home_score and away_score >= 0.45:
        return away
    return ''


def _market(row: dict[str, Any]) -> str:
    text = _clean(row.get('market_type') or row.get('market') or row.get('prediction'))
    if 'spread' in text:
        return 'spreads'
    if 'total' in text or 'over' in text or 'under' in text:
        return 'totals'
    return 'h2h'


def _grade_pick(ledger_row: dict[str, Any], result_row: dict[str, Any]) -> tuple[str, str]:
    prediction = safe_text(ledger_row.get('prediction') or ledger_row.get('pick') or ledger_row.get('selection'))
    market = _market(ledger_row)
    home = safe_text(result_row.get('home_team'))
    away = safe_text(result_row.get('away_team'))
    home_score = _float(result_row.get('home_score'))
    away_score = _float(result_row.get('away_score'))
    winner = safe_text(result_row.get('winner')) or _winner(home, away, home_score, away_score)
    if home_score is None or away_score is None:
        return 'pending', 'missing_score'
    if market == 'h2h':
        if not winner:
            return 'void', 'draw_no_winner'
        return ('win', 'winner_match') if _sim(prediction, winner) >= 0.70 else ('loss', 'winner_mismatch')
    line = _float(ledger_row.get('line_point') or ledger_row.get('line'))
    if market == 'spreads':
        selected = _selected_team(prediction, home, away)
        if not selected or line is None:
            return 'pending', 'spread_needs_review'
        if _sim(selected, home) >= 0.90:
            margin = float(home_score) - float(away_score) + float(line)
        else:
            margin = float(away_score) - float(home_score) + float(line)
        if margin > 0:
            return 'win', 'spread_cover'
        if margin < 0:
            return 'loss', 'spread_no_cover'
        return 'void', 'spread_push'
    if market == 'totals':
        if line is None:
            return 'pending', 'total_needs_review'
        total = float(home_score) + float(away_score)
        pred = _clean(prediction)
        if 'over' in pred:
            if total > float(line):
                return 'win', 'total_over_hit'
            if total < float(line):
                return 'loss', 'total_over_miss'
            return 'void', 'total_push'
        if 'under' in pred:
            if total < float(line):
                return 'win', 'total_under_hit'
            if total > float(line):
                return 'loss', 'total_under_miss'
            return 'void', 'total_push'
        return 'pending', 'total_side_needs_review'
    return 'pending', 'unknown_market'


def _match_event(ledger_row: dict[str, Any], result_rows: list[dict[str, Any]], threshold: float) -> tuple[dict[str, Any] | None, float]:
    best = None
    best_score = 0.0
    ledger_event = safe_text(ledger_row.get('event'))
    ledger_sport = safe_text(ledger_row.get('sport') or ledger_row.get('sport_key'))
    ledger_date = _date_prefix(ledger_row.get('event_start_utc') or ledger_row.get('commence_time') or ledger_row.get('start'))
    for result in result_rows:
        event_score = _sim(ledger_event, result.get('event'))
        sport_score = max(_sim(ledger_sport, result.get('sport')), _sim(ledger_row.get('sport_key'), result.get('sport_key')))
        result_date = _date_prefix(result.get('event_start_utc'))
        date_score = 1.0 if ledger_date and result_date and ledger_date == result_date else 0.0
        score = event_score * 0.70 + sport_score * 0.15 + date_score * 0.15
        if score > best_score:
            best_score = score
            best = result
    if best is not None and best_score >= float(threshold):
        return best, best_score
    return None, best_score


def pending_sport_keys(ledger: pd.DataFrame) -> list[str]:
    if ledger.empty:
        return []
    rows = []
    for row in ledger.to_dict(orient='records'):
        status = _clean(row.get('result_status'))
        if status in RESOLVED_STATUSES:
            continue
        key = safe_text(row.get('sport_key'))
        if key and key not in rows:
            rows.append(key)
    return rows


def fetch_completed_results(api_key: str, sport_keys: list[str], *, days_from: int = 3) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    errors: dict[str, str] = {}
    for sport_key in sport_keys:
        try:
            payload = _get_json(f'/v4/sports/{sport_key}/scores/', {'apiKey': api_key, 'daysFrom': int(days_from), 'dateFormat': 'iso'})
            frame = odds_scores_to_result_frame(payload)
            if not frame.empty:
                frames.append(frame)
        except Exception as exc:
            errors[sport_key] = str(exc)[:240]
    if not frames:
        return pd.DataFrame(), {'sport_keys': sport_keys, 'errors': errors, 'result_rows': 0}
    results = pd.concat(frames, ignore_index=True, sort=False).drop_duplicates()
    return results, {'sport_keys': sport_keys, 'errors': errors, 'result_rows': int(len(results))}


def apply_fuzzy_result_updates(ledger: pd.DataFrame, results: pd.DataFrame, *, threshold: float = 0.86) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = filter_locked_proof_rows(ledger)
    if locked.empty or results.empty:
        return locked, {'updated_rows': 0, 'matched_rows': 0, 'needs_review': 0}
    result_rows = results.to_dict(orient='records')
    updated_rows: list[dict[str, Any]] = []
    updated = 0
    matched = 0
    needs_review = 0
    wins = losses = voids = 0
    for row in locked.to_dict(orient='records'):
        item = dict(row)
        status = _clean(item.get('result_status'))
        if status in RESOLVED_STATUSES:
            updated_rows.append(item)
            continue
        match, confidence = _match_event(item, result_rows, threshold)
        item['auto_result_match_confidence'] = round(confidence, 4)
        if match is None:
            item['auto_result_status'] = 'needs_review_no_match'
            needs_review += 1
            updated_rows.append(item)
            continue
        matched += 1
        result, reason = _grade_pick(item, match)
        item['auto_result_status'] = reason
        item['matched_event'] = safe_text(match.get('event'))
        item['winner'] = safe_text(match.get('winner'))
        item['final_score'] = safe_text(match.get('final_score'))
        item['home_score'] = match.get('home_score')
        item['away_score'] = match.get('away_score')
        if result in {'win', 'loss', 'void'}:
            item['result_status'] = result
            item['graded_at_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            updated += 1
            wins += int(result == 'win')
            losses += int(result == 'loss')
            voids += int(result == 'void')
        else:
            needs_review += 1
        updated_rows.append(item)
    frame = filter_locked_proof_rows(pd.DataFrame(updated_rows))
    return frame, {'updated_rows': updated, 'matched_rows': matched, 'needs_review': needs_review, 'wins_added': wins, 'losses_added': losses, 'voids_added': voids}


def run_auto_result_sync(
    workspace_id: Any = 'test_01',
    *,
    api_key_override: str = '',
    days_from: int = 3,
    threshold: float = 0.86,
    run_learning_after: bool = True,
) -> dict[str, Any]:
    ledger = load_persistent_ledger(workspace_id=workspace_id)
    locked = filter_locked_proof_rows(ledger)
    sports = pending_sport_keys(locked)
    report: dict[str, Any] = {'version': 'auto-result-sync-v1', 'workspace_id': safe_text(workspace_id), 'locked_rows': int(len(locked)), 'pending_sport_keys': sports}
    if locked.empty:
        report.update({'status': 'skipped', 'reason': 'no_locked_rows'})
        return report
    if not sports:
        report.update({'status': 'skipped', 'reason': 'no_pending_sport_keys'})
        return report
    results, fetch_report = fetch_completed_results(_api_key(api_key_override), sports, days_from=int(days_from))
    report['fetch'] = fetch_report
    if results.empty:
        report.update({'status': 'skipped', 'reason': 'no_completed_results_found'})
        return report
    updated, stats = apply_fuzzy_result_updates(locked, results, threshold=float(threshold))
    report['grading'] = stats
    if not updated.empty:
        save_persistent_ledger(updated, workspace_id=workspace_id)
    if run_learning_after and int(stats.get('updated_rows') or 0) > 0:
        report['learning'] = run_auto_learning_cycle(workspace_id, save_to_github=True)
    report['status'] = 'updated' if int(stats.get('updated_rows') or 0) > 0 else 'no_updates'
    return report

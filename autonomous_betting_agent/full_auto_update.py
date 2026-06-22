from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from .commercial_platform_tools import filter_locked_proof_rows, latest_active_list, load_persistent_ledger
from .dashboard_sync import sync_dashboard_state
from .live_odds import _get_json, validate_api_key
from .result_grading_v2 import apply_fuzzy_updates, odds_scores_to_result_frame_v2
from .row_normalizer import safe_text

ESPN_SCOREBOARD_MAP = {
    'baseball_mlb': ('baseball', 'mlb'),
    'basketball_nba': ('basketball', 'nba'),
    'basketball_wnba': ('basketball', 'wnba'),
    'americanfootball_nfl': ('football', 'nfl'),
    'icehockey_nhl': ('hockey', 'nhl'),
    'soccer_epl': ('soccer', 'eng.1'),
}
ODDS_API_MAX_SCORE_DAYS_FROM = 3
PROTECTED_RESULT_FIELDS = ['result_status', 'winner', 'final_score', 'graded_at_utc', 'profit_units']
RESULT_COMPARE_FIELDS = ['result_status', 'winner', 'final_score', 'profit_units']


def get_api_key(override: str = '') -> str:
    key = safe_text(override)
    if key:
        return validate_api_key(key)
    try:
        import streamlit as st
        key = safe_text(st.secrets.get('THE_ODDS_API_KEY', '') or st.secrets.get('ODDS_API_KEY', ''))
    except Exception:
        key = ''
    if not key:
        key = os.getenv('THE_ODDS_API_KEY', '') or os.getenv('ODDS_API_KEY', '')
    return validate_api_key(key)


def sport_keys_from_ledger(frame: pd.DataFrame | list[dict[str, Any]]) -> list[str]:
    ledger = filter_locked_proof_rows(frame)
    keys: set[str] = set()
    for col in ('sport_key', 'sport'):
        if col in ledger.columns:
            for value in ledger[col].dropna().astype(str):
                text = value.strip()
                if text and '_' in text:
                    keys.add(text)
    return sorted(keys)


def _public_error(exc: Exception) -> str:
    text = str(exc)
    if 'apiKey=' in text:
        text = text.split('apiKey=', 1)[0] + 'apiKey=<hidden>'
    return text[:240]


def _score_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _team_name(competitor: dict[str, Any]) -> str:
    team = competitor.get('team') or {}
    return safe_text(team.get('displayName') or team.get('shortDisplayName') or team.get('name') or competitor.get('id'))


def _espn_event_row(event: dict[str, Any], sport_key: str) -> dict[str, Any] | None:
    competitions = event.get('competitions') or []
    if not competitions:
        return None
    competition = competitions[0] or {}
    competitors = competition.get('competitors') or []
    home = away = None
    for competitor in competitors:
        side = safe_text(competitor.get('homeAway')).lower()
        if side == 'home':
            home = competitor
        elif side == 'away':
            away = competitor
    if home is None or away is None:
        return None
    status = event.get('status') or {}
    status_type = status.get('type') or {}
    completed = bool(status_type.get('completed')) or safe_text(status_type.get('state')).lower() == 'post'
    if not completed:
        return None
    home_team = _team_name(home)
    away_team = _team_name(away)
    home_score = _score_int(home.get('score'))
    away_score = _score_int(away.get('score'))
    if not home_team or not away_team or home_score is None or away_score is None:
        return None
    winner = ''
    if home.get('winner') is True or home_score > away_score:
        winner = home_team
    elif away.get('winner') is True or away_score > home_score:
        winner = away_team
    result_status = 'void' if home_score == away_score else 'final'
    return {
        'event': f'{away_team} at {home_team}',
        'sport_key': sport_key,
        'sport': sport_key,
        'event_start_utc': safe_text(event.get('date')),
        'home_team': home_team,
        'away_team': away_team,
        'home_score': home_score,
        'away_score': away_score,
        'winner': winner,
        'result_status': result_status,
        'final_score': f'{away_team} {away_score} - {home_score} {home_team}',
        'result_source': 'espn_scoreboard_fallback',
    }


def fetch_espn_completed_scores(sport_key: str, *, days_from: int = 7) -> pd.DataFrame:
    mapping = ESPN_SCOREBOARD_MAP.get(sport_key)
    if not mapping:
        return pd.DataFrame()
    sport, league = mapping
    rows: list[dict[str, Any]] = []
    today = datetime.now(timezone.utc).date()
    for offset in range(max(1, int(days_from))):
        day = today - timedelta(days=offset)
        url = f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard'
        try:
            response = requests.get(url, params={'dates': day.strftime('%Y%m%d')}, timeout=12)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue
        for event in payload.get('events') or []:
            row = _espn_event_row(event, sport_key)
            if row is not None:
                rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=['event', 'event_start_utc', 'sport_key'])


def _merge_result_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame()
    merged = pd.concat(valid, ignore_index=True, sort=False)
    dedupe_cols = [col for col in ['event', 'event_start_utc', 'sport_key', 'winner', 'final_score'] if col in merged.columns]
    return merged.drop_duplicates(subset=dedupe_cols or None)


def fetch_completed_scores_for_ledger(ledger: pd.DataFrame | list[dict[str, Any]], *, api_key: str, days_from: int = 7, sport_key: str = '') -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    locked = filter_locked_proof_rows(ledger)
    keys = [safe_text(sport_key)] if safe_text(sport_key) else sport_keys_from_ledger(locked)
    frames: list[pd.DataFrame] = []
    stats: list[dict[str, Any]] = []
    requested_days = max(1, int(days_from))
    odds_days = min(requested_days, ODDS_API_MAX_SCORE_DAYS_FROM)
    for key in keys:
        if not key:
            continue
        sport_frames: list[pd.DataFrame] = []
        odds_error = ''
        try:
            payload = _get_json(f'/v4/sports/{key}/scores/', {'apiKey': api_key, 'daysFrom': odds_days, 'dateFormat': 'iso'})
            odds_frame = odds_scores_to_result_frame_v2(payload)
            if not odds_frame.empty:
                sport_frames.append(odds_frame)
            odds_status = 'ok'
        except Exception as exc:
            odds_status = 'skipped_error'
            odds_error = _public_error(exc)
        espn_frame = fetch_espn_completed_scores(key, days_from=requested_days)
        if not espn_frame.empty:
            sport_frames.append(espn_frame)
        combined = _merge_result_frames(sport_frames)
        if not combined.empty:
            source = 'the_odds_api_scores'
            status = 'ok'
            if odds_status != 'ok' and not espn_frame.empty:
                source = 'espn_scoreboard_fallback'
                status = 'ok_fallback'
            elif odds_status == 'ok' and not espn_frame.empty and requested_days > odds_days:
                source = 'the_odds_api_scores+espn_scoreboard_fallback'
                status = 'ok_augmented'
            item = {'sport_key': key, 'result_rows': int(len(combined)), 'status': status, 'source': source, 'requested_days': requested_days, 'odds_api_days_from': odds_days}
            if odds_error:
                item['odds_api_error'] = odds_error
            stats.append(item)
            frames.append(combined)
        else:
            item = {'sport_key': key, 'result_rows': 0, 'status': 'skipped_error', 'source': 'none', 'requested_days': requested_days, 'odds_api_days_from': odds_days}
            if odds_error:
                item['error'] = odds_error
            stats.append(item)
    return _merge_result_frames(frames), stats


def _status_counts(frame: pd.DataFrame) -> dict[str, int]:
    if frame is None or frame.empty or 'result_status' not in frame.columns:
        return {'wins': 0, 'losses': 0, 'voids': 0, 'resolved': 0}
    status = frame['result_status'].astype(str).str.lower()
    wins = int(status.eq('win').sum())
    losses = int(status.eq('loss').sum())
    voids = int(status.isin(['void', 'push', 'cancelled', 'canceled']).sum())
    return {'wins': wins, 'losses': losses, 'voids': voids, 'resolved': wins + losses + voids}


def _row_key(row: dict[str, Any]) -> str:
    proof_id = safe_text(row.get('proof_id'))
    if proof_id:
        return f'proof:{proof_id}'
    return '|'.join([safe_text(row.get('event')).lower(), safe_text(row.get('prediction')).lower(), safe_text(row.get('event_start_utc'))[:10]])


def _protect_existing_wins(original: pd.DataFrame, proposed: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if original.empty or proposed.empty:
        return proposed, 0
    original_by_key = {_row_key(row): row for row in original.to_dict(orient='records')}
    rows = []
    protected = 0
    for row in proposed.to_dict(orient='records'):
        item = dict(row)
        old = original_by_key.get(_row_key(item))
        if old and safe_text(old.get('result_status')).lower() == 'win' and safe_text(item.get('result_status')).lower() != 'win':
            for field in PROTECTED_RESULT_FIELDS:
                if field in old:
                    item[field] = old.get(field)
            item['grading_match_status'] = 'protected_existing_win'
            item['protected_auto_downgrade'] = True
            protected += 1
        rows.append(item)
    return pd.DataFrame(rows), protected


def _changed_rows(before: pd.DataFrame, after: pd.DataFrame) -> int:
    if before.empty or after.empty:
        return 0
    before_by_key = {_row_key(row): row for row in before.to_dict(orient='records')}
    changed = 0
    for row in after.to_dict(orient='records'):
        old = before_by_key.get(_row_key(row))
        if old is None:
            continue
        for field in RESULT_COMPARE_FIELDS:
            if safe_text(old.get(field)) != safe_text(row.get(field)):
                changed += 1
                break
    return changed


def _active_identity(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {'active_list_id': '', 'active_list_rows': 0}
    out: dict[str, Any] = {'active_list_rows': int(len(frame))}
    for col in ['active_list_id', 'ledger_batch_id', 'list_id', 'source_file']:
        if col in frame.columns:
            values = frame[col].map(safe_text)
            nonempty = values[values.ne('')]
            if not nonempty.empty:
                out[col] = nonempty.iloc[-1]
    if 'locked_at_utc' in frame.columns:
        parsed = pd.to_datetime(frame['locked_at_utc'], errors='coerce', utc=True)
        if parsed.notna().any():
            out['locked_at_min'] = parsed.min().isoformat()
            out['locked_at_max'] = parsed.max().isoformat()
    return out


def full_update_and_sync(*, workspace_id: Any = '', api_key_override: str = '', days_from: int = 7, sport_key: str = '') -> tuple[pd.DataFrame, dict[str, Any]]:
    ledger_all = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    locked = latest_active_list(ledger_all)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'actual_changed_rows': 0, 'reason': 'empty_ledger', 'locked_rows': 0}
    before_counts = _status_counts(locked)
    results, sport_stats = fetch_completed_scores_for_ledger(locked, api_key=get_api_key(api_key_override), days_from=days_from, sport_key=sport_key)
    updated, stats = apply_fuzzy_updates(locked, results, regrade_resolved=True)
    protected_wins = 0
    actual_changed = 0
    if not updated.empty:
        updated, protected_wins = _protect_existing_wins(locked, updated)
        actual_changed = _changed_rows(locked, updated)
        if actual_changed > 0:
            updated = sync_dashboard_state(updated, workspace_id=workspace_id)
    after_counts = _status_counts(updated if not updated.empty else locked)
    ok_sports = [item for item in sport_stats if str(item.get('status', '')).startswith('ok')]
    errored_sports = [item for item in sport_stats if not str(item.get('status', '')).startswith('ok')]
    if results.empty and errored_sports and not ok_sports:
        reason = 'all_score_feeds_failed_or_unsupported'
    elif results.empty:
        reason = 'no_completed_results_found'
    elif int(stats.get('matched_rows') or 0) <= 0:
        reason = 'completed_results_found_but_no_ledger_matches'
    elif actual_changed <= 0:
        reason = 'matches_found_but_no_new_changes'
    else:
        reason = 'results_updated'
    stats.update({
        'locked_rows': int(len(locked)),
        'all_workspace_rows': int(len(ledger_all)),
        'active_list_only': True,
        'active_list_identity': _active_identity(locked),
        'sports_checked': sport_stats,
        'score_feed_errors': errored_sports,
        'total_result_rows': int(len(results)),
        'workspace_id': safe_text(workspace_id) or 'default',
        'regraded_resolved_rows': True,
        'protected_existing_wins': protected_wins,
        'actual_changed_rows': actual_changed,
        'before_counts': before_counts,
        'after_counts': after_counts,
        'reason': reason,
    })
    return updated if not updated.empty else locked, stats

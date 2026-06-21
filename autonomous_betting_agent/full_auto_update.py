from __future__ import annotations

import os
from typing import Any

import pandas as pd

from .commercial_platform_tools import filter_locked_proof_rows, load_persistent_ledger
from .dashboard_sync import sync_dashboard_state
from .live_odds import _get_json, validate_api_key
from .result_grading_v2 import apply_fuzzy_updates, odds_scores_to_result_frame_v2
from .row_normalizer import safe_text


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


def fetch_completed_scores_for_ledger(
    ledger: pd.DataFrame | list[dict[str, Any]],
    *,
    api_key: str,
    days_from: int = 7,
    sport_key: str = '',
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    locked = filter_locked_proof_rows(ledger)
    keys = [safe_text(sport_key)] if safe_text(sport_key) else sport_keys_from_ledger(locked)
    frames: list[pd.DataFrame] = []
    stats: list[dict[str, Any]] = []
    for key in keys:
        if not key:
            continue
        try:
            payload = _get_json(f'/v4/sports/{key}/scores/', {'apiKey': api_key, 'daysFrom': int(days_from), 'dateFormat': 'iso'})
            frame = odds_scores_to_result_frame_v2(payload)
            stats.append({'sport_key': key, 'result_rows': int(len(frame)), 'status': 'ok'})
            if not frame.empty:
                frames.append(frame)
        except Exception as exc:
            stats.append({'sport_key': key, 'result_rows': 0, 'status': 'skipped_error', 'error': _public_error(exc)})
            continue
    results = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    return results, stats


def full_update_and_sync(
    *,
    workspace_id: Any = '',
    api_key_override: str = '',
    days_from: int = 7,
    sport_key: str = '',
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ledger = load_persistent_ledger(workspace_id=workspace_id)
    locked = filter_locked_proof_rows(ledger)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'reason': 'empty_ledger', 'locked_rows': 0}
    results, sport_stats = fetch_completed_scores_for_ledger(
        locked,
        api_key=get_api_key(api_key_override),
        days_from=days_from,
        sport_key=sport_key,
    )
    updated, stats = apply_fuzzy_updates(locked, results)
    if not updated.empty:
        updated = sync_dashboard_state(updated, workspace_id=workspace_id)
    ok_sports = [item for item in sport_stats if item.get('status') == 'ok']
    errored_sports = [item for item in sport_stats if item.get('status') != 'ok']
    reason = ''
    if results.empty and errored_sports and not ok_sports:
        reason = 'all_score_feeds_failed_or_unsupported'
    elif results.empty:
        reason = 'no_completed_results_found'
    elif int(stats.get('updated_rows') or 0) <= 0:
        reason = 'completed_results_found_but_no_ledger_matches'
    stats.update({
        'locked_rows': int(len(locked)),
        'sports_checked': sport_stats,
        'score_feed_errors': errored_sports,
        'total_result_rows': int(len(results)),
        'workspace_id': safe_text(workspace_id) or 'default',
    })
    if reason:
        stats['reason'] = reason
    return updated, stats

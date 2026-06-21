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
        payload = _get_json(f'/v4/sports/{key}/scores/', {'apiKey': api_key, 'daysFrom': int(days_from), 'dateFormat': 'iso'})
        frame = odds_scores_to_result_frame_v2(payload)
        stats.append({'sport_key': key, 'result_rows': int(len(frame))})
        if not frame.empty:
            frames.append(frame)
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
    if ledger.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'reason': 'empty_ledger'}
    results, sport_stats = fetch_completed_scores_for_ledger(
        ledger,
        api_key=get_api_key(api_key_override),
        days_from=days_from,
        sport_key=sport_key,
    )
    updated, stats = apply_fuzzy_updates(ledger, results)
    if not updated.empty:
        updated = sync_dashboard_state(updated, workspace_id=workspace_id)
    stats.update({'sports_checked': sport_stats, 'total_result_rows': int(len(results)), 'workspace_id': safe_text(workspace_id) or 'default'})
    return updated, stats

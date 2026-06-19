from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / 'data'
HELD_KEYS = {
    'what_are_the_odds_latest_rows',
    'pro_predictor_latest_rows',
    'pro_predictor_high_confidence_rows',
    'ara_latest_predictions',
    'odds_lock_pro_locked_rows',
    'public_proof_dashboard_refresh_rows',
}


def normalize_workspace_id(value: Any = 'test_01') -> str:
    text = str(value or 'test_01').strip().lower()
    cleaned = ''.join(char if char.isalnum() or char in {'-', '_'} else '_' for char in text)
    cleaned = '_'.join(part for part in cleaned.split('_') if part)
    return cleaned[:48] or 'test_01'


def _path_for(key: str, workspace_id: Any = 'test_01') -> Path:
    workspace = normalize_workspace_id(workspace_id)
    safe_key = ''.join(char if char.isalnum() or char in {'-', '_'} else '_' for char in str(key))
    return DATA_DIR / f'held_picks_{workspace}_{safe_key}.json'


def rows_from_any(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return []
        return value.to_dict(orient='records')
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def save_held_rows(key: str, rows: Any, workspace_id: Any = 'test_01') -> int:
    if key not in HELD_KEYS:
        return 0
    cleaned = rows_from_any(rows)
    if not cleaned:
        return 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {'version': 'held-picks-v2', 'workspace_id': normalize_workspace_id(workspace_id), 'key': key, 'rows': cleaned}
    _path_for(key, workspace_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return len(cleaned)


def load_held_rows(key: str, workspace_id: Any = 'test_01') -> list[dict[str, Any]]:
    path = _path_for(key, workspace_id)
    try:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding='utf-8'))
        rows = payload.get('rows', [])
        return [dict(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def load_first_available(keys: list[str] | tuple[str, ...], workspace_id: Any = 'test_01') -> tuple[str, list[dict[str, Any]]]:
    for key in keys:
        rows = load_held_rows(key, workspace_id)
        if rows:
            return key, rows
    return '', []

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
_FALLBACK_MEMORY: dict[str, list[dict[str, Any]]] = {}


def _memory_store() -> dict[str, list[dict[str, Any]]]:
    """Process-level store that survives Streamlit page changes and reruns."""
    try:
        import streamlit as st

        @st.cache_resource(show_spinner=False)
        def _cached_store() -> dict[str, list[dict[str, Any]]]:
            return {}

        return _cached_store()
    except Exception:
        return _FALLBACK_MEMORY


def normalize_workspace_id(value: Any = 'test_01') -> str:
    text = str(value or 'test_01').strip().lower()
    cleaned = ''.join(char if char.isalnum() or char in {'-', '_'} else '_' for char in text)
    cleaned = '_'.join(part for part in cleaned.split('_') if part)
    return cleaned[:48] or 'test_01'


def _store_key(key: str, workspace_id: Any = 'test_01') -> str:
    return f'{normalize_workspace_id(workspace_id)}::{key}'


def _safe_key(key: str) -> str:
    return ''.join(char if char.isalnum() or char in {'-', '_'} else '_' for char in str(key))


def _path_for(key: str, workspace_id: Any = 'test_01') -> Path:
    workspace = normalize_workspace_id(workspace_id)
    return DATA_DIR / f'held_picks_{workspace}_{_safe_key(key)}.json'


def _backup_path_for(key: str, workspace_id: Any = 'test_01') -> Path:
    workspace = normalize_workspace_id(workspace_id)
    return DATA_DIR / f'held_picks_{workspace}_{_safe_key(key)}.backup.json'


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


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    tmp.replace(path)


def save_held_rows(key: str, rows: Any, workspace_id: Any = 'test_01') -> int:
    if key not in HELD_KEYS:
        return 0
    workspace = normalize_workspace_id(workspace_id)
    cleaned = rows_from_any(rows)
    store = _memory_store()
    store[_store_key(key, workspace)] = cleaned
    if workspace != 'test_01':
        store[_store_key(key, 'test_01')] = cleaned
    store[_store_key(f'latest_{key}', 'test_01')] = cleaned
    try:
        payload = {'version': 'held-picks-v4-local-memory', 'workspace_id': workspace, 'key': key, 'rows': cleaned}
        _write_payload(_path_for(key, workspace), payload)
        _write_payload(_backup_path_for(key, workspace), payload)
        if workspace != 'test_01':
            _write_payload(_path_for(key, 'test_01'), {'version': 'held-picks-v4-local-memory', 'workspace_id': 'test_01', 'key': key, 'rows': cleaned})
        _write_payload(_path_for(f'latest_{key}', 'test_01'), {'version': 'held-picks-v4-local-memory', 'workspace_id': 'test_01', 'key': f'latest_{key}', 'rows': cleaned})
    except Exception:
        pass
    return len(cleaned)


def _load_payload(path: Path) -> list[dict[str, Any]]:
    try:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding='utf-8'))
        rows = payload.get('rows', [])
        return [dict(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def load_held_rows(key: str, workspace_id: Any = 'test_01') -> list[dict[str, Any]]:
    if key not in HELD_KEYS:
        return []
    workspace = normalize_workspace_id(workspace_id)
    store = _memory_store()
    for lookup_key, lookup_workspace in [
        (key, workspace),
        (key, 'test_01'),
        (f'latest_{key}', 'test_01'),
    ]:
        memory_rows = store.get(_store_key(lookup_key, lookup_workspace), [])
        if memory_rows:
            return [dict(row) for row in memory_rows if isinstance(row, dict)]
        for path in [_path_for(lookup_key, lookup_workspace), _backup_path_for(lookup_key, lookup_workspace)]:
            rows = _load_payload(path)
            if rows:
                store[_store_key(lookup_key, lookup_workspace)] = rows
                return rows
    try:
        safe = _safe_key(key)
        for path in sorted(DATA_DIR.glob(f'held_picks_*_{safe}.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            rows = _load_payload(path)
            if rows:
                store[_store_key(key, workspace)] = rows
                return rows
    except Exception:
        pass
    return []


def load_first_available(keys: list[str] | tuple[str, ...], workspace_id: Any = 'test_01') -> tuple[str, list[dict[str, Any]]]:
    for key in keys:
        rows = load_held_rows(key, workspace_id)
        if rows:
            return key, rows
    return '', []

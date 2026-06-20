from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests

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
GITHUB_API = 'https://api.github.com'
GITHUB_STATE_DIR = '.aba_state'
GITHUB_CHUNK_SIZE = 50


def _memory_store() -> dict[str, list[dict[str, Any]]]:
    try:
        import streamlit as st

        @st.cache_resource(show_spinner=False)
        def _cached_store() -> dict[str, list[dict[str, Any]]]:
            return {}

        return _cached_store()
    except Exception:
        return _FALLBACK_MEMORY


def _secret_value(*names: str) -> str:
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


def _github_token() -> str:
    return _secret_value('GITHUB_PROOF_TOKEN', 'PROOF_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN')


def _github_repo() -> str:
    return _secret_value('GITHUB_PROOF_REPO', 'PROOF_GITHUB_REPO', 'GITHUB_REPOSITORY') or 'BoneManTGRM/autonomous-betting-agent'


def _github_branch() -> str:
    return _secret_value('GITHUB_PROOF_BRANCH', 'PROOF_GITHUB_BRANCH') or 'main'


def github_store_enabled() -> bool:
    return bool(_github_token() and _github_repo())


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


def _github_path(key: str, workspace_id: Any = 'test_01') -> str:
    workspace = normalize_workspace_id(workspace_id)
    return f'{GITHUB_STATE_DIR}/held_picks_{workspace}_{_safe_key(key)}.json'


def _github_index_path(key: str, workspace_id: Any = 'test_01') -> str:
    workspace = normalize_workspace_id(workspace_id)
    return f'{GITHUB_STATE_DIR}/held_picks_{workspace}_{_safe_key(key)}.index.json'


def _github_part_path(key: str, workspace_id: Any, part: int) -> str:
    workspace = normalize_workspace_id(workspace_id)
    return f'{GITHUB_STATE_DIR}/held_picks_{workspace}_{_safe_key(key)}.part{part:04d}.json'


def _github_headers(token: str) -> dict[str, str]:
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


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


def _empty_payload(key: str, workspace_id: Any = 'test_01') -> dict[str, Any]:
    return {'version': 'held-picks-v7-github-chunked', 'workspace_id': normalize_workspace_id(workspace_id), 'key': key, 'rows': []}


def _github_get_json(path: str) -> tuple[dict[str, Any], str, int]:
    token = _github_token()
    repo = _github_repo()
    branch = _github_branch()
    if not token or not repo:
        return {}, '', 0
    url = f'{GITHUB_API}/repos/{repo}/contents/{path}'
    try:
        response = requests.get(url, headers=_github_headers(token), params={'ref': branch}, timeout=20)
        if response.status_code == 404:
            return {}, '', 404
        status = response.status_code
        response.raise_for_status()
        payload = response.json()
        encoded = str(payload.get('content', '')).replace('\n', '')
        decoded = base64.b64decode(encoded).decode('utf-8')
        return json.loads(decoded), str(payload.get('sha', '')), status
    except Exception:
        return {}, '', 0


def _github_put_json(path: str, payload: dict[str, Any], message: str) -> bool:
    token = _github_token()
    repo = _github_repo()
    branch = _github_branch()
    if not token or not repo:
        return False
    _existing, sha, _status = _github_get_json(path)
    content = base64.b64encode((json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n').encode('utf-8')).decode('ascii')
    body: dict[str, Any] = {'message': message, 'content': content, 'branch': branch}
    if sha:
        body['sha'] = sha
    url = f'{GITHUB_API}/repos/{repo}/contents/{path}'
    try:
        response = requests.put(url, headers=_github_headers(token), json=body, timeout=30)
        response.raise_for_status()
        return True
    except Exception:
        return False


def _github_get_payload(key: str, workspace_id: Any = 'test_01') -> tuple[list[dict[str, Any]], str]:
    index_payload, index_sha, _ = _github_get_json(_github_index_path(key, workspace_id))
    if index_payload.get('format') == 'chunked':
        rows: list[dict[str, Any]] = []
        part_count = int(index_payload.get('parts') or 0)
        for part in range(part_count):
            part_payload, _part_sha, _ = _github_get_json(_github_part_path(key, workspace_id, part))
            part_rows = part_payload.get('rows', [])
            rows.extend([dict(row) for row in part_rows if isinstance(row, dict)])
        return rows, index_sha
    payload, sha, _ = _github_get_json(_github_path(key, workspace_id))
    rows = payload.get('rows', [])
    return [dict(row) for row in rows if isinstance(row, dict)], sha


def _github_save_payload(key: str, rows: list[dict[str, Any]], workspace_id: Any = 'test_01') -> bool:
    if not github_store_enabled():
        return False
    workspace = normalize_workspace_id(workspace_id)
    parts = [rows[index:index + GITHUB_CHUNK_SIZE] for index in range(0, len(rows), GITHUB_CHUNK_SIZE)] or [[]]
    ok = True
    for part_index, part_rows in enumerate(parts):
        ok = _github_put_json(
            _github_part_path(key, workspace, part_index),
            {'version': 'held-picks-v7-github-chunked', 'format': 'chunk', 'workspace_id': workspace, 'key': key, 'part': part_index, 'rows': part_rows},
            f'Persist {key} part {part_index} for {workspace}',
        ) and ok
    index_payload = {
        'version': 'held-picks-v7-github-chunked',
        'format': 'chunked',
        'workspace_id': workspace,
        'key': key,
        'parts': len(parts),
        'rows_count': len(rows),
        'chunk_size': GITHUB_CHUNK_SIZE,
    }
    ok = _github_put_json(_github_index_path(key, workspace), index_payload, f'Persist {key} index for {workspace}') and ok
    return ok


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
        payload = {'version': 'held-picks-v7-github-chunked', 'workspace_id': workspace, 'key': key, 'rows': cleaned}
        _write_payload(_path_for(key, workspace), payload)
        _write_payload(_backup_path_for(key, workspace), payload)
        if workspace != 'test_01':
            _write_payload(_path_for(key, 'test_01'), {'version': 'held-picks-v7-github-chunked', 'workspace_id': 'test_01', 'key': key, 'rows': cleaned})
        _write_payload(_path_for(f'latest_{key}', 'test_01'), {'version': 'held-picks-v7-github-chunked', 'workspace_id': 'test_01', 'key': f'latest_{key}', 'rows': cleaned})
    except Exception:
        pass
    try:
        _github_save_payload(key, cleaned, workspace)
        if workspace != 'test_01':
            _github_save_payload(key, cleaned, 'test_01')
        if key in {'odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows', 'ara_latest_predictions'}:
            _github_save_payload(f'latest_{key}', cleaned, 'test_01')
    except Exception:
        pass
    return len(cleaned)


def clear_held_rows(key: str, workspace_id: Any = 'test_01') -> int:
    if key not in HELD_KEYS:
        return 0
    workspace = normalize_workspace_id(workspace_id)
    aliases = [(key, workspace), (key, 'test_01'), (f'latest_{key}', 'test_01')]
    store = _memory_store()
    for alias_key, alias_workspace in aliases:
        store[_store_key(alias_key, alias_workspace)] = []
        try:
            _write_payload(_path_for(alias_key, alias_workspace), _empty_payload(alias_key, alias_workspace))
            _write_payload(_backup_path_for(alias_key, alias_workspace), _empty_payload(alias_key, alias_workspace))
        except Exception:
            pass
        try:
            _github_save_payload(alias_key, [], alias_workspace)
        except Exception:
            pass
    return 1


def clear_all_held_rows(workspace_id: Any = 'test_01') -> int:
    return sum(clear_held_rows(key, workspace_id) for key in sorted(HELD_KEYS))


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
        rows, _sha = _github_get_payload(lookup_key, lookup_workspace)
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


def verify_held_rows(key: str, rows: Any, workspace_id: Any = 'test_01') -> dict[str, Any]:
    expected = len(rows_from_any(rows))
    saved = save_held_rows(key, rows, workspace_id)
    reloaded = len(load_held_rows(key, workspace_id))
    ok = expected == saved == reloaded
    return {
        'key': key,
        'workspace_id': normalize_workspace_id(workspace_id),
        'expected_rows': expected,
        'saved_rows': saved,
        'reloaded_rows': reloaded,
        'ok': ok,
        'github_store_enabled': github_store_enabled(),
        'message': 'save_reload_ok' if ok else 'save_reload_mismatch',
    }


def store_snapshot(workspace_id: Any = 'test_01') -> pd.DataFrame:
    workspace = normalize_workspace_id(workspace_id)
    rows: list[dict[str, Any]] = []
    for key in sorted(HELD_KEYS):
        exact_path = _path_for(key, workspace)
        backup_path = _backup_path_for(key, workspace)
        github_rows, _sha = _github_get_payload(key, workspace)
        rows.append({
            'workspace_id': workspace,
            'key': key,
            'loaded_rows': len(load_held_rows(key, workspace)),
            'disk_rows': len(_load_payload(exact_path)),
            'backup_rows': len(_load_payload(backup_path)),
            'github_rows': len(github_rows),
            'github_enabled': github_store_enabled(),
            'disk_file_exists': exact_path.exists(),
            'backup_file_exists': backup_path.exists(),
            'disk_file': str(exact_path),
            'github_path': _github_index_path(key, workspace),
        })
    return pd.DataFrame(rows)

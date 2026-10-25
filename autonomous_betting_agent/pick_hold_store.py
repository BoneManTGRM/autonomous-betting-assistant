from __future__ import annotations

import base64
import json
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
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
PROOF_KEYS = {'odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows'}
LATEST_ALIAS_KEYS = {'what_are_the_odds_latest_rows', 'pro_predictor_latest_rows', 'pro_predictor_high_confidence_rows', 'ara_latest_predictions'}
_FALLBACK_MEMORY: dict[str, list[dict[str, Any]]] = {}
GITHUB_API = 'https://api.github.com'
GITHUB_STATE_DIR = '.aba_state'
GITHUB_CHUNK_SIZE = 50



@dataclass
class RemoteReadBudget:
    """Ephemeral render state; unavailable must not be presented as an empty ledger."""

    deadline: float
    unavailable: bool = False
    requests: int = 0
    responses: dict = field(default_factory=dict)


_REMOTE_READ_BUDGET: ContextVar[RemoteReadBudget | None] = ContextVar('held_remote_read_budget', default=None)


@contextmanager
def remote_read_budget():
    """Bound automatic reads for one render, never writes or other callers.

    Five seconds is an elapsed admission budget, not a hard wall-clock guarantee:
    Requests connect/read timeouts cannot interrupt every DNS or slow-trickle case.
    Each new context retries afresh; no unavailable result is cached globally.
    """
    state = RemoteReadBudget(deadline=time.monotonic() + 5.0)
    token = _REMOTE_READ_BUDGET.set(state)
    try:
        yield state
    finally:
        _REMOTE_READ_BUDGET.reset(token)


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


def _clean_key(value: Any) -> str:
    return ' '.join(str(value or '').strip().lower().replace('-', ' ').replace('_', ' ').split())


def _row_identity(row: dict[str, Any]) -> tuple[str, ...]:
    proof_id = _clean_key(row.get('proof_id'))
    if proof_id:
        return ('proof_id', proof_id)
    stable = _clean_key(row.get('stable_pick_key') or row.get('source_pick_key') or row.get('pick_key'))
    if stable:
        return ('stable', stable)
    event_id = _clean_key(row.get('event_id') or row.get('game_id') or row.get('fixture_id'))
    if event_id:
        return (
            'event_id',
            event_id,
            _clean_key(row.get('market_type') or row.get('market')),
            _clean_key(row.get('line_point') or row.get('line')),
            _clean_key(row.get('prediction') or row.get('pick') or row.get('selection')),
        )
    return (
        'event',
        _clean_key(row.get('event') or row.get('event_name') or row.get('game') or row.get('match')),
        _clean_key(row.get('sport') or row.get('sport_key') or row.get('league')),
        _clean_key(row.get('market_type') or row.get('market')),
        _clean_key(row.get('line_point') or row.get('line')),
        _clean_key(row.get('prediction') or row.get('pick') or row.get('selection')),
        _clean_key(row.get('event_start_utc') or row.get('commence_time') or row.get('start')),
    )


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, ...], dict[str, Any]] = {}
    order: list[tuple[str, ...]] = []
    for raw in rows:
        row = dict(raw)
        key = _row_identity(row)
        if key not in deduped:
            order.append(key)
        deduped[key] = row
    return [deduped[key] for key in order]


def rows_from_any(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return []
        return dedupe_rows(value.to_dict(orient='records'))
    if isinstance(value, list):
        return dedupe_rows([dict(row) for row in value if isinstance(row, dict)])
    return []


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    tmp.replace(path)


def _empty_payload(key: str, workspace_id: Any = 'test_01') -> dict[str, Any]:
    return {'version': 'held-picks-v8-deduped', 'workspace_id': normalize_workspace_id(workspace_id), 'key': key, 'rows': []}


def _github_get_json(path: str, *, use_read_budget: bool = True) -> tuple[dict[str, Any], str, int]:
    token = _github_token()
    repo = _github_repo()
    branch = _github_branch()
    if not token or not repo:
        return {}, '', 0
    state = _REMOTE_READ_BUDGET.get() if use_read_budget else None
    cache_key = (repo, branch, token, path)
    timeout: Any = 20
    if state is not None:
        if cache_key in state.responses:
            return state.responses[cache_key]
        remaining = state.deadline - time.monotonic()
        if state.unavailable or remaining <= 0 or state.requests >= 64:
            state.unavailable = True
            return {}, '', 0
        timeout = (min(2.5, remaining / 2), min(2.5, remaining / 2))
        state.requests += 1
    url = f'{GITHUB_API}/repos/{repo}/contents/{path}'
    try:
        response = requests.get(url, headers=_github_headers(token), params={'ref': branch}, timeout=timeout)
        if response.status_code == 404:
            result = ({}, '', 404)
        else:
            status = response.status_code
            response.raise_for_status()
            payload = response.json()
            encoded = str(payload.get('content', '')).replace('\n', '')
            decoded = base64.b64decode(encoded).decode('utf-8')
            decoded_payload = json.loads(decoded)
            if state is not None and not isinstance(decoded_payload, dict):
                raise ValueError('Remote saved-row payload must be an object')
            result = (decoded_payload, str(payload.get('sha', '')), status)
        if state is not None:
            state.responses[cache_key] = result
        return result
    except Exception:
        if state is not None:
            state.unavailable = True
        return {}, '', 0


def _github_put_json(path: str, payload: dict[str, Any], message: str) -> bool:
    token = _github_token()
    repo = _github_repo()
    branch = _github_branch()
    if not token or not repo:
        return False
    _existing, sha, _status = _github_get_json(path, use_read_budget=False)
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
    state = _REMOTE_READ_BUDGET.get()
    if index_payload.get('format') == 'chunked':
        if state is not None:
            parts = index_payload.get('parts')
            if type(parts) is not int or not 1 <= parts <= 64:
                state.unavailable = True
                return [], ''
        rows: list[dict[str, Any]] = []
        part_count = int(index_payload.get('parts') or 0)
        for part in range(part_count):
            part_payload, _part_sha, part_status = _github_get_json(_github_part_path(key, workspace_id, part))
            state = _REMOTE_READ_BUDGET.get()
            if state is not None and (state.unavailable or part_status != 200):
                state.unavailable = True
                return [], ''
            if state is not None and (not isinstance(part_payload.get('rows'), list) or not all(isinstance(row, dict) for row in part_payload['rows'])):
                state.unavailable = True
                return [], ''
            part_rows = part_payload.get('rows', [])
            rows.extend([dict(row) for row in part_rows if isinstance(row, dict)])
        return dedupe_rows(rows), index_sha
    payload, sha, status = _github_get_json(_github_path(key, workspace_id))
    if state is not None and status == 200 and (not isinstance(payload.get('rows'), list) or not all(isinstance(row, dict) for row in payload['rows'])):
        state.unavailable = True
        return [], ''
    rows = payload.get('rows', [])
    return dedupe_rows([dict(row) for row in rows if isinstance(row, dict)]), sha


def _github_save_payload(key: str, rows: list[dict[str, Any]], workspace_id: Any = 'test_01') -> bool:
    if not github_store_enabled():
        return False
    workspace = normalize_workspace_id(workspace_id)
    cleaned = dedupe_rows(rows)
    old_index, _old_sha, _ = _github_get_json(_github_index_path(key, workspace), use_read_budget=False)
    old_parts = int(old_index.get('parts') or 0) if old_index.get('format') == 'chunked' else 0
    parts = [cleaned[index:index + GITHUB_CHUNK_SIZE] for index in range(0, len(cleaned), GITHUB_CHUNK_SIZE)] or [[]]
    ok = True
    for part_index, part_rows in enumerate(parts):
        ok = _github_put_json(
            _github_part_path(key, workspace, part_index),
            {'version': 'held-picks-v8-deduped', 'format': 'chunk', 'workspace_id': workspace, 'key': key, 'part': part_index, 'rows': part_rows},
            f'Persist {key} part {part_index} for {workspace}',
        ) and ok
    for stale_part in range(len(parts), old_parts):
        ok = _github_put_json(
            _github_part_path(key, workspace, stale_part),
            {'version': 'held-picks-v8-deduped', 'format': 'chunk', 'workspace_id': workspace, 'key': key, 'part': stale_part, 'rows': []},
            f'Clear stale {key} part {stale_part} for {workspace}',
        ) and ok
    index_payload = {
        'version': 'held-picks-v8-deduped',
        'format': 'chunked',
        'workspace_id': workspace,
        'key': key,
        'parts': len(parts),
        'rows_count': len(cleaned),
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
    if key in LATEST_ALIAS_KEYS:
        store[_store_key(f'latest_{key}', workspace)] = cleaned
    try:
        payload = {'version': 'held-picks-v8-deduped', 'workspace_id': workspace, 'key': key, 'rows': cleaned}
        _write_payload(_path_for(key, workspace), payload)
        _write_payload(_backup_path_for(key, workspace), payload)
        if key in LATEST_ALIAS_KEYS:
            _write_payload(_path_for(f'latest_{key}', workspace), {'version': 'held-picks-v8-deduped', 'workspace_id': workspace, 'key': f'latest_{key}', 'rows': cleaned})
    except Exception:
        pass
    try:
        _github_save_payload(key, cleaned, workspace)
        if key in LATEST_ALIAS_KEYS:
            _github_save_payload(f'latest_{key}', cleaned, workspace)
    except Exception:
        pass
    return len(cleaned)


def clear_held_rows(key: str, workspace_id: Any = 'test_01') -> int:
    if key not in HELD_KEYS:
        return 0
    workspace = normalize_workspace_id(workspace_id)
    aliases = [(key, workspace)]
    if key in LATEST_ALIAS_KEYS:
        aliases.append((f'latest_{key}', workspace))
    if workspace != 'test_01':
        aliases.append((key, 'test_01'))
        aliases.append((f'latest_{key}', 'test_01'))
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
        return dedupe_rows([dict(row) for row in rows if isinstance(row, dict)])
    except Exception:
        return []


def _candidate_lookups(key: str, workspace: str) -> list[tuple[str, str]]:
    lookups = [(key, workspace)]
    if key in LATEST_ALIAS_KEYS:
        lookups.append((f'latest_{key}', workspace))
    return lookups


def load_held_rows(key: str, workspace_id: Any = 'test_01') -> list[dict[str, Any]]:
    if key not in HELD_KEYS:
        return []
    workspace = normalize_workspace_id(workspace_id)
    store = _memory_store()
    for lookup_key, lookup_workspace in _candidate_lookups(key, workspace):
        memory_rows = dedupe_rows(store.get(_store_key(lookup_key, lookup_workspace), []))
        if memory_rows:
            return memory_rows
        for path in [_path_for(lookup_key, lookup_workspace), _backup_path_for(lookup_key, lookup_workspace)]:
            rows = _load_payload(path)
            if rows:
                store[_store_key(lookup_key, lookup_workspace)] = rows
                return rows
        rows, _sha = _github_get_payload(lookup_key, lookup_workspace)
        if rows:
            store[_store_key(lookup_key, lookup_workspace)] = rows
            return rows
    return []


def load_github_held_rows(key: str, workspace_id: Any = 'test_01') -> list[dict[str, Any]]:
    if key not in HELD_KEYS:
        return []
    workspace = normalize_workspace_id(workspace_id)
    rows, _sha = _github_get_payload(key, workspace)
    return rows


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

from __future__ import annotations

from typing import Any

_PATCH_VERSION = 'proof_persistence_repo_target_v1'
DEFAULT_PROOF_REPO = 'BoneManTGRM/autonomous-betting-assistant'
_LAST_DIAGNOSTICS: dict[str, Any] = {}


def install_proof_persistence_patch() -> None:
    """Make proof ledger storage durable across Streamlit reboots.

    The original held-row store defaulted to BoneManTGRM/autonomous-betting-agent.
    This app runs from BoneManTGRM/autonomous-betting-assistant, so when a token was
    present but no explicit GITHUB_PROOF_REPO was configured, cloud persistence wrote
    to the wrong repo or failed silently. This patch changes the default durable store
    target to the current repo and keeps the existing local/session fallbacks.
    """
    try:
        from autonomous_betting_agent import pick_hold_store as store
    except Exception:
        return
    if getattr(store, '_ABA_PROOF_PERSISTENCE_PATCH_VERSION', '') == _PATCH_VERSION:
        return

    def github_token() -> str:
        return store._secret_value(
            'GITHUB_PROOF_TOKEN',
            'PROOF_GITHUB_TOKEN',
            'GH_TOKEN',
            'GITHUB_TOKEN',
            'GITHUB_PAT',
            'PERSONAL_ACCESS_TOKEN',
        )

    def github_repo() -> str:
        return store._secret_value(
            'GITHUB_PROOF_REPO',
            'PROOF_GITHUB_REPO',
            'GITHUB_STATE_REPO',
            'GITHUB_REPO',
            'GITHUB_REPOSITORY',
        ) or DEFAULT_PROOF_REPO

    def github_branch() -> str:
        return store._secret_value('GITHUB_PROOF_BRANCH', 'PROOF_GITHUB_BRANCH', 'GITHUB_BRANCH') or 'main'

    def github_store_enabled() -> bool:
        return bool(github_token() and github_repo())

    original_save = store.save_held_rows
    original_load = store.load_held_rows

    def save_held_rows(key: str, rows: Any, workspace_id: Any = 'test_01') -> int:
        saved = original_save(key, rows, workspace_id)
        _LAST_DIAGNOSTICS.clear()
        _LAST_DIAGNOSTICS.update({
            'key': key,
            'workspace_id': store.normalize_workspace_id(workspace_id),
            'saved_rows': int(saved),
            'github_store_enabled': github_store_enabled(),
            'github_repo': github_repo(),
            'github_branch': github_branch(),
            'patch_version': _PATCH_VERSION,
        })
        return saved

    def load_held_rows(key: str, workspace_id: Any = 'test_01') -> list[dict[str, Any]]:
        rows = original_load(key, workspace_id)
        _LAST_DIAGNOSTICS.update({
            'last_load_key': key,
            'last_load_workspace_id': store.normalize_workspace_id(workspace_id),
            'last_load_rows': len(rows),
            'github_store_enabled': github_store_enabled(),
            'github_repo': github_repo(),
            'github_branch': github_branch(),
            'patch_version': _PATCH_VERSION,
        })
        return rows

    def proof_persistence_diagnostics() -> dict[str, Any]:
        return {
            **_LAST_DIAGNOSTICS,
            'github_store_enabled': github_store_enabled(),
            'github_repo': github_repo(),
            'github_branch': github_branch(),
            'patch_version': _PATCH_VERSION,
        }

    store._github_token = github_token
    store._github_repo = github_repo
    store._github_branch = github_branch
    store.github_store_enabled = github_store_enabled
    store.save_held_rows = save_held_rows
    store.load_held_rows = load_held_rows
    store.proof_persistence_diagnostics = proof_persistence_diagnostics
    store._ABA_PROOF_PERSISTENCE_PATCH_VERSION = _PATCH_VERSION

    try:
        from autonomous_betting_agent import commercial_platform_tools as commercial
        commercial.load_held_rows = load_held_rows
        commercial.save_held_rows = save_held_rows
    except Exception:
        pass


install_proof_persistence_patch()

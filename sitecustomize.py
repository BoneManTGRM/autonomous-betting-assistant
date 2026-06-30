from __future__ import annotations

import builtins
import importlib
import os
import sys
from types import ModuleType
from typing import Any

_TARGET = "autonomous_betting_agent.magazine_book_export"
_ORIGINAL_IMPORT = builtins.__import__
_ORIGINAL_RELOAD = importlib.reload


def get_secret(*names: str) -> str:
    """Read secrets without exposing key values."""
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                raw = st.secrets.get(name, '')
                value = str(raw.strip()) if hasattr(raw, 'strip') else str(raw).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def _patch_proof_persistence_repo() -> None:
    try:
        from autonomous_betting_agent.proof_persistence_patch import install_proof_persistence_patch
        install_proof_persistence_patch()
    except Exception:
        pass


def _patch_proof_hold_store() -> None:
    _patch_proof_persistence_repo()
    try:
        from autonomous_betting_agent import pick_hold_store as phs
        from autonomous_betting_agent.row_normalizer import result_status
    except Exception:
        return
    if getattr(phs, '_aba_proof_hold_merge_v2', False):
        return
    original_load = phs.load_held_rows
    original_save = phs.save_held_rows

    def proof_rank(row: dict[str, Any]) -> int:
        status = result_status(row)
        if status in {'win', 'loss'}:
            return 5
        if status in {'void', 'push'}:
            return 4
        if status == 'needs_review':
            return 3
        if str(row.get('graded_at_utc') or '').strip():
            return 2
        return 1

    def proof_dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_key: dict[tuple[str, ...], dict[str, Any]] = {}
        order: list[tuple[str, ...]] = []
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            key = phs._row_identity(row)
            if key not in by_key:
                by_key[key] = row
                order.append(key)
            elif proof_rank(row) >= proof_rank(by_key[key]):
                by_key[key] = row
        return [by_key[key] for key in order]

    def merged_load_held_rows(key: str, workspace_id: Any = 'test_01') -> list[dict[str, Any]]:
        if key not in phs.HELD_KEYS:
            return []
        if key not in phs.PROOF_KEYS:
            return original_load(key, workspace_id)
        workspace = phs.normalize_workspace_id(workspace_id)
        store = phs._memory_store()
        rows: list[dict[str, Any]] = []
        for lookup_key, lookup_workspace in phs._candidate_lookups(key, workspace):
            rows.extend(phs.dedupe_rows(store.get(phs._store_key(lookup_key, lookup_workspace), [])))
            for path in [phs._path_for(lookup_key, lookup_workspace), phs._backup_path_for(lookup_key, lookup_workspace)]:
                rows.extend(phs._load_payload(path))
            try:
                github_rows, _sha = phs._github_get_payload(lookup_key, lookup_workspace)
                rows.extend(github_rows)
            except Exception:
                pass
        merged = proof_dedupe(rows)
        if merged:
            store[phs._store_key(key, workspace)] = merged
        return merged

    def merged_save_held_rows(key: str, rows: Any, workspace_id: Any = 'test_01') -> int:
        if key not in phs.HELD_KEYS:
            return 0
        if key not in phs.PROOF_KEYS:
            return original_save(key, rows, workspace_id)
        incoming = phs.rows_from_any(rows)
        existing = merged_load_held_rows(key, workspace_id)
        return original_save(key, proof_dedupe(existing + incoming), workspace_id)

    phs.load_held_rows = merged_load_held_rows
    phs.save_held_rows = merged_save_held_rows
    phs._aba_proof_hold_merge_v2 = True


def _patch_commercial_pending_proof_mask() -> None:
    try:
        import pandas as pd
        from autonomous_betting_agent import commercial_platform_tools as cpt
        from autonomous_betting_agent import pick_hold_store as phs
    except Exception:
        return
    if getattr(cpt, '_aba_pending_proof_mask_runtime_v4', False):
        return
    cpt.load_held_rows = phs.load_held_rows
    cpt.save_held_rows = phs.save_held_rows

    def guarded_lock_ready_mask(frame):
        if frame.empty:
            return pd.Series(dtype=bool)
        mask = pd.Series(False, index=frame.index)
        for field in ['lock_ready', 'official_lock_ready', 'research_lock_ready', 'profit_volume_safe']:
            if field in frame.columns:
                mask = mask | frame[field].map(cpt._truthy).fillna(False)
        if 'verified_grade' in frame.columns:
            mask = mask | frame['verified_grade'].map(cpt.safe_text).str.lower().isin(['win', 'loss', 'void', 'push', 'needs_review'])
        if 'result_status' in frame.columns:
            mask = mask | frame['result_status'].map(cpt.safe_text).str.lower().isin(['win', 'loss', 'void', 'push', 'needs_review'])
        return mask

    cpt._lock_ready_mask = guarded_lock_ready_mask
    cpt._aba_pending_proof_mask_runtime_v4 = True


def _install_report_cleanup(module: ModuleType | None = None) -> ModuleType | None:
    try:
        from autonomous_betting_agent.magazine_report_cleanup_patch import install_live_cleanup, install_renderer_cleanup
        install_live_cleanup()
        return install_renderer_cleanup(module) if module is not None else module
    except Exception:
        return module


def _apply_if_target(module: ModuleType | None) -> ModuleType | None:
    if module is None or getattr(module, '__name__', '') != _TARGET:
        return module
    try:
        from autonomous_betting_agent.magazine_api_sources import apply_magazine_api_patch
        from autonomous_betting_agent.magazine_auto_sizer import apply_magazine_auto_sizer
        from autonomous_betting_agent.magazine_combo_section_patch import install as install_combo_section
        from autonomous_betting_agent.magazine_footer_cleanup import install as install_footer_cleanup
        from autonomous_betting_agent.magazine_headline_safety import install as install_headline_safety
        from autonomous_betting_agent.magazine_live_api_enrichment import install as install_live_api_enrichment
        from autonomous_betting_agent.magazine_parlay_footer_override import install as install_parlay_footer_override
        from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
        from autonomous_betting_agent.magazine_truth_status_patch import install as install_truth_status_patch
        from autonomous_betting_agent.spanish_magazine_fixes import install as install_spanish_magazine_fixes

        module = apply_magazine_api_patch(module)
        module = install_live_api_enrichment(module)
        module = _install_report_cleanup(module) or module
        module = apply_magazine_auto_sizer(module)
        module = install_headline_safety(module)
        module = apply_magazine_sale_ready_patch(module)
        module = install_truth_status_patch(module) or module
        module = install_footer_cleanup(module)
        module = install_combo_section(module)
        module = install_parlay_footer_override(module)
        module = install_truth_status_patch(module) or module
        module = _install_report_cleanup(module) or module
        install_spanish_magazine_fixes()
        return module
    except Exception:
        return module


def _patched_import(name: str, globals: dict[str, Any] | None = None, locals: dict[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    imported = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
    if name == _TARGET or name.startswith(f'{_TARGET}.') or (name == 'autonomous_betting_agent' and 'magazine_book_export' in fromlist):
        _apply_if_target(sys.modules.get(_TARGET))
    if name == 'autonomous_betting_agent.pick_hold_store' or (name == 'autonomous_betting_agent' and 'pick_hold_store' in fromlist):
        _patch_proof_hold_store()
    if name == 'autonomous_betting_agent.magazine_live_api_enrichment' or (name == 'autonomous_betting_agent' and 'magazine_live_api_enrichment' in fromlist):
        _install_report_cleanup(None)
    if name == 'autonomous_betting_agent.commercial_platform_tools' or (name == 'autonomous_betting_agent' and 'commercial_platform_tools' in fromlist):
        _patch_proof_hold_store()
        _patch_commercial_pending_proof_mask()
    return imported


def _patched_reload(module: ModuleType) -> ModuleType:
    reloaded = _ORIGINAL_RELOAD(module)
    name = getattr(reloaded, '__name__', '')
    if name == _TARGET:
        reloaded = _apply_if_target(reloaded) or reloaded
    if name == 'autonomous_betting_agent.pick_hold_store':
        _patch_proof_hold_store()
    if name == 'autonomous_betting_agent.magazine_live_api_enrichment':
        _install_report_cleanup(None)
    if name == 'autonomous_betting_agent.commercial_platform_tools':
        _patch_proof_hold_store()
        _patch_commercial_pending_proof_mask()
    return reloaded


builtins.get_secret = get_secret
if getattr(builtins, '_ABA_MAGAZINE_IMPORT_AND_RELOAD_PATCHED_V3', False) is not True:
    builtins.__import__ = _patched_import
    importlib.reload = _patched_reload
    builtins._ABA_MAGAZINE_IMPORT_AND_RELOAD_PATCHED_V3 = True

_patch_proof_hold_store()
_patch_commercial_pending_proof_mask()
_install_report_cleanup(None)
_apply_if_target(sys.modules.get(_TARGET))

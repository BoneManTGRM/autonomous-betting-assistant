from __future__ import annotations

import builtins
import importlib
import os

# Runtime bridges only. No secret values are printed or exposed.
# This file intentionally does not monkey-patch Streamlit widgets.


def get_secret(*names: str) -> str:
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if st is not None:
            try:
                value = str(st.secrets.get(name, '') or '').strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret


def _runtime_disabled() -> bool:
    return os.getenv('GITHUB_ACTIONS', '').lower() in {'1', 'true', 'yes'} or os.getenv('ABA_DISABLE_RUNTIME_PATCHES', '').lower() in {'1', 'true', 'yes'}


def _apply_balldontlie_bridge(module: object | None = None) -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.balldontlie_integration import install
        install(module)
    except Exception:
        pass
    try:
        from autonomous_betting_agent.api_registry_runtime_patch import install as install_registry
        install_registry()
    except Exception:
        pass


def _apply_parlay_intelligence_bridge(module: object | None = None) -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.parlay_intelligence_patch import install
        install(module)
    except Exception:
        pass


def _apply_magazine_export_state_guard(module: object | None = None) -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.magazine_export_state_guard import install
        install(module)
    except Exception:
        pass


def _apply_report_studio_bootstrap_bridge() -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.report_studio_bootstrap import install
        install()
    except Exception:
        pass


def _apply_magazine_display_bridge(module: object | None = None) -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.magazine_second_page_patch import install
        install(module)
    except Exception:
        pass
    try:
        from autonomous_betting_agent.magazine_regression_guard import install as install_regression_guard
        install_regression_guard(module)
    except Exception:
        pass
    _apply_balldontlie_bridge(module)
    _apply_parlay_intelligence_bridge(module)
    _apply_magazine_export_state_guard(module)
    _apply_report_studio_bootstrap_bridge()


def _install_report_source_quality_guard() -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.report_source_quality_guard import install
        install()
    except Exception:
        pass


def _install_proof_ledger_integrity_guard() -> None:
    if _runtime_disabled():
        return
    try:
        import pandas as pd
        import autonomous_betting_agent.commercial_platform_tools as cpt
        from autonomous_betting_agent.odds_lock_tools import lock_status, proof_hash, update_profit_columns
        from autonomous_betting_agent.row_normalizer import normalize_frame, result_status, safe_text
    except Exception:
        return
    if getattr(cpt, '_ABA_PROOF_LEDGER_INTEGRITY_GUARD_V1', False):
        return

    def _timestamped_rows(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty or 'locked_at_utc' not in frame.columns:
            return pd.DataFrame()
        return frame[frame['locked_at_utc'].map(safe_text).ne('')].copy()

    def strict_filter_locked_proof_rows(frame):
        raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
        out = cpt._canonicalize_result_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
        out = update_profit_columns(out) if not out.empty else pd.DataFrame()
        if out.empty:
            return pd.DataFrame()
        if 'event_start_time' in out.columns and 'event_start_utc' not in out.columns:
            out['event_start_utc'] = out['event_start_time']
        if cpt.PROOF_REQUIRED_COLUMNS.issubset(out.columns):
            proof = out[out['proof_id'].map(safe_text).ne('') & out['locked_at_utc'].map(safe_text).ne('')].copy()
            if not proof.empty:
                return cpt._ensure_lock_identity(proof)
        mask = cpt._lock_ready_mask(out)
        if mask.empty or not bool(mask.any()):
            return pd.DataFrame()
        candidate = cpt._ensure_lock_identity(out[mask].copy())
        return _timestamped_rows(candidate)

    def strict_proof_audit_frame(frame):
        locked = cpt.latest_active_list(frame)
        rows = []
        for r in locked.to_dict('records'):
            h = safe_text(r.get('proof_hash'))
            try:
                rh = proof_hash(r)
            except Exception:
                rh = ''
            hs = 'hash_match' if h and h == rh else 'hash_mismatch'
            ls = safe_text(r.get('proof_status')) or lock_status(r)
            has_lock_time = bool(safe_text(r.get('locked_at_utc')))
            au = 'pass' if has_lock_time and hs == 'hash_match' and ls == 'locked_before_start' else 'review'
            rows.append({
                'proof_id': safe_text(r.get('proof_id')),
                'event': safe_text(r.get('event')),
                'prediction': safe_text(r.get('prediction')),
                'locked_at_utc': safe_text(r.get('locked_at_utc')),
                'event_start_utc': safe_text(r.get('event_start_utc')),
                'hash_status': hs,
                'lock_status': ls,
                'audit_status': au,
                'proof_source_type': safe_text(r.get('proof_source_type')),
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=['proof_id', 'hash_status', 'lock_status', 'audit_status'])

    cpt.filter_locked_proof_rows = strict_filter_locked_proof_rows
    cpt.proof_audit_frame = strict_proof_audit_frame
    cpt._ABA_PROOF_LEDGER_INTEGRITY_GUARD_V1 = True


def _install_magazine_reload_bridge() -> None:
    if _runtime_disabled() or getattr(importlib.reload, '_ABA_MAGAZINE_DIRECT_BRIDGE', False):
        return
    original_reload = getattr(importlib, '_aba_original_reload', importlib.reload)
    setattr(importlib, '_aba_original_reload', original_reload)

    def reload_with_magazine_bridge(module: object) -> object:
        reloaded = original_reload(module)
        if getattr(reloaded, '__name__', '') == 'autonomous_betting_agent.magazine_book_export':
            _apply_magazine_display_bridge(reloaded)
        return reloaded

    reload_with_magazine_bridge._ABA_MAGAZINE_DIRECT_BRIDGE = True
    importlib.reload = reload_with_magazine_bridge


def _install_magazine_polish_bridge() -> None:
    if _runtime_disabled():
        return
    try:
        import autonomous_betting_agent.magazine_report_polish_patch as polish
    except Exception:
        return
    original_install = getattr(polish, 'install', None)
    if not callable(original_install) or getattr(original_install, '_ABA_MAGAZINE_DIRECT_BRIDGE', False):
        return

    def install_and_guard(*args: object, **kwargs: object) -> object:
        result = original_install(*args, **kwargs)
        _apply_magazine_display_bridge()
        return result

    install_and_guard._ABA_MAGAZINE_DIRECT_BRIDGE = True
    polish.install = install_and_guard


def _install_magazine_export_state_bridge() -> None:
    if _runtime_disabled():
        return
    try:
        import autonomous_betting_agent.magazine_sale_ready_patch as sale_ready
    except Exception:
        return
    original_apply = getattr(sale_ready, 'apply_magazine_sale_ready_patch', None)
    if not callable(original_apply) or getattr(original_apply, '_ABA_EXPORT_STATE_BRIDGE', False):
        return

    def apply_sale_ready_and_export_guard(module: object) -> object:
        patched = original_apply(module)
        _apply_magazine_export_state_guard(patched)
        _apply_report_studio_bootstrap_bridge()
        return patched

    apply_sale_ready_and_export_guard._ABA_EXPORT_STATE_BRIDGE = True
    sale_ready.apply_magazine_sale_ready_patch = apply_sale_ready_and_export_guard


_install_report_source_quality_guard()
_install_proof_ledger_integrity_guard()
_install_magazine_reload_bridge()
_install_magazine_polish_bridge()
_install_magazine_export_state_bridge()
_apply_magazine_display_bridge()

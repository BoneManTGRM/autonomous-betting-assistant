from __future__ import annotations

from typing import Any

_PATCHED = False

HANDOFF_KEYS = (
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "pro_predictor_high_confidence_rows",
    "pro_predictor_latest_rows",
    "what_are_the_odds_latest_rows",
    "ara_latest_predictions",
)


def _rowish(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    sample = [item for item in value[:5] if isinstance(item, dict)]
    if not sample:
        return False
    keys = {str(key).lower() for item in sample for key in item.keys()}
    hints = {"event", "event_name", "game", "matchup", "selection", "sport", "market_type", "confidence"}
    return bool(keys & hints)


def _has_fresh_handoff_rows() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False
    try:
        for key in HANDOFF_KEYS:
            rows = st.session_state.get(key) or []
            if _rowish(rows):
                st.session_state["report_studio_preferred_source"] = f"session:{key}"
                return True
        for key, value in list(st.session_state.items()):
            text_key = str(key)
            if text_key.startswith("report_studio_"):
                continue
            if _rowish(value):
                st.session_state["report_studio_preferred_source"] = f"session:{text_key}"
                return True
    except Exception:
        return False
    return False


def install() -> None:
    global _PATCHED
    if _PATCHED:
        return
    try:
        from autonomous_betting_agent import commercial_platform_tools as cpt
    except Exception:
        return
    original_load_persistent_ledger = getattr(cpt, "load_persistent_ledger", None)
    if not callable(original_load_persistent_ledger):
        return

    def load_persistent_ledger_fresh_safe(*args: Any, **kwargs: Any):
        if _has_fresh_handoff_rows():
            try:
                import pandas as pd
                return pd.DataFrame()
            except Exception:
                return None
        return original_load_persistent_ledger(*args, **kwargs)

    load_persistent_ledger_fresh_safe._ABA_FRESH_HANDOFF_PATCH = True
    cpt.load_persistent_ledger = load_persistent_ledger_fresh_safe
    _PATCHED = True


install()

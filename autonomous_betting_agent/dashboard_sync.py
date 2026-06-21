from __future__ import annotations

from typing import Any

import pandas as pd

from .commercial_platform_tools import filter_locked_proof_rows, save_persistent_ledger
from .pick_hold_store import save_held_rows

SESSION_LEDGER_KEYS = ('odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows')


def sync_dashboard_state(frame: pd.DataFrame | list[dict[str, Any]], workspace_id: Any = '') -> pd.DataFrame:
    cleaned = filter_locked_proof_rows(frame)
    if cleaned.empty:
        return pd.DataFrame()
    saved = save_persistent_ledger(cleaned, workspace_id=workspace_id)
    rows = saved.to_dict(orient='records') if not saved.empty else cleaned.to_dict(orient='records')
    for key in SESSION_LEDGER_KEYS:
        save_held_rows(key, rows, workspace_id)
    try:
        import streamlit as st
        for key in SESSION_LEDGER_KEYS:
            st.session_state[key] = rows
    except Exception:
        pass
    return saved if not saved.empty else cleaned

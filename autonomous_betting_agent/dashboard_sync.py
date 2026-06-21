from __future__ import annotations

from typing import Any

import pandas as pd

from .commercial_platform_tools import filter_locked_proof_rows, save_persistent_ledger

SESSION_LEDGER_KEYS = ('odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows')


def sync_dashboard_state(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    cleaned = filter_locked_proof_rows(frame)
    if cleaned.empty:
        return pd.DataFrame()
    save_persistent_ledger(cleaned)
    try:
        import streamlit as st
        rows = cleaned.to_dict(orient='records')
        for key in SESSION_LEDGER_KEYS:
            st.session_state[key] = rows
    except Exception:
        pass
    return cleaned

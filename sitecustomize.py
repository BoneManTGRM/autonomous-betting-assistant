from __future__ import annotations

import builtins
import os

# Keep this lightweight: Python imports sitecustomize before Streamlit pages.
# Runtime hooks stay disabled in CI, but production loads the current-row routing
# before Report Studio binds its ledger imports.


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
                raw = st.secrets.get(name, "")
                value = str(raw.strip()) if hasattr(raw, "strip") else str(raw).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


builtins.get_secret = get_secret

if os.getenv("CI", "").lower() not in {"1", "true", "yes"}:
    try:
        from autonomous_betting_agent.report_studio_fresh_handoff_patch import install as install_current_run_routing
        install_current_run_routing()
    except Exception:
        pass

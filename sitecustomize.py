from __future__ import annotations

import builtins
import os

# This file intentionally does not monkey-patch Streamlit widgets.
# Keep it lightweight: Python imports sitecustomize before CI compile/import
# checks, so runtime app behavior should live in app/page code instead.


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

from __future__ import annotations

import builtins
import os


def get_secret(*names: str) -> str:
    """Read a secret from Streamlit secrets first, then environment variables.

    This file intentionally does not monkey-patch Streamlit widgets. Uploaders,
    buttons, forms, text inputs, radios, and selectboxes must stay native so the
    app remains stable on mobile and desktop.
    """
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, '').strip()) if hasattr(st.secrets.get(name, ''), 'strip') else str(st.secrets.get(name, '')).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret

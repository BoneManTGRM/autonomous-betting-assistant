from __future__ import annotations

import builtins
import importlib
import os
from types import ModuleType

_TARGET = "autonomous_betting_agent.magazine_book_export"
_ORIGINAL_RELOAD = importlib.reload


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


def _apply_if_target(module: ModuleType | None) -> ModuleType | None:
    if module is None or getattr(module, "__name__", "") != _TARGET:
        return module
    try:
        from autonomous_betting_agent.magazine_api_sources import apply_magazine_api_patch
        from autonomous_betting_agent.magazine_auto_sizer import apply_magazine_auto_sizer
        from autonomous_betting_agent.magazine_headline_safety import install as install_headline_safety

        module = apply_magazine_api_patch(module)
        module = apply_magazine_auto_sizer(module)
        return install_headline_safety(module)
    except Exception:
        return module


def _patched_reload(module: ModuleType) -> ModuleType:
    reloaded = _ORIGINAL_RELOAD(module)
    return _apply_if_target(reloaded) or reloaded


builtins.get_secret = get_secret
if getattr(builtins, "_ABA_DYNAMIC_MAGAZINE_RELOAD_PATCHED", False) is not True:
    importlib.reload = _patched_reload
    builtins._ABA_DYNAMIC_MAGAZINE_RELOAD_PATCHED = True

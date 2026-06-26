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
        from autonomous_betting_agent.magazine_live_api_enrichment import install as install_live_api_enrichment

        module = apply_magazine_api_patch(module)
        module = install_live_api_enrichment(module)
        module = apply_magazine_auto_sizer(module)
        return install_headline_safety(module)
    except Exception:
        return module


def _patched_import(name: str, globals: dict[str, Any] | None = None, locals: dict[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
    imported = _ORIGINAL_IMPORT(name, globals, fromlist=fromlist, locals=locals, level=level)
    if name == _TARGET or name.startswith(f"{_TARGET}.") or (name == "autonomous_betting_agent" and "magazine_book_export" in fromlist):
        _apply_if_target(sys.modules.get(_TARGET))
    return imported


def _patched_reload(module: ModuleType) -> ModuleType:
    reloaded = _ORIGINAL_RELOAD(module)
    return _apply_if_target(reloaded) or reloaded


builtins.get_secret = get_secret
if getattr(builtins, "_ABA_MAGAZINE_IMPORT_AND_RELOAD_PATCHED", False) is not True:
    builtins.__import__ = _patched_import
    importlib.reload = _patched_reload
    builtins._ABA_MAGAZINE_IMPORT_AND_RELOAD_PATCHED = True

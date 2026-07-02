from __future__ import annotations

import builtins
import importlib
import os

# This file intentionally does not monkey-patch Streamlit widgets.
# Keep Streamlit widget behavior native. Runtime helpers are limited to
# secret lookup and magazine/report runtime repair after module reloads.


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


def _runtime_disabled() -> bool:
    return os.getenv("GITHUB_ACTIONS", "").lower() in {"1", "true", "yes"} or os.getenv("ABA_DISABLE_RUNTIME_PATCHES", "").lower() in {"1", "true", "yes"}


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


def _install_report_source_quality_guard() -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.report_source_quality_guard import install
        install()
    except Exception:
        pass


def _install_magazine_reload_bridge() -> None:
    if _runtime_disabled() or getattr(importlib.reload, "_ABA_MAGAZINE_DIRECT_BRIDGE", False):
        return
    original_reload = getattr(importlib, "_aba_original_reload", importlib.reload)
    setattr(importlib, "_aba_original_reload", original_reload)

    def reload_with_magazine_bridge(module: object) -> object:
        reloaded = original_reload(module)
        if getattr(reloaded, "__name__", "") == "autonomous_betting_agent.magazine_book_export":
            _apply_magazine_display_bridge(reloaded)
        return reloaded

    reload_with_magazine_bridge._ABA_MAGAZINE_DIRECT_BRIDGE = True  # type: ignore[attr-defined]
    importlib.reload = reload_with_magazine_bridge


def _install_magazine_polish_bridge() -> None:
    if _runtime_disabled():
        return
    try:
        import autonomous_betting_agent.magazine_report_polish_patch as polish
    except Exception:
        return
    original_install = getattr(polish, "install", None)
    if not callable(original_install) or getattr(original_install, "_ABA_MAGAZINE_DIRECT_BRIDGE", False):
        return

    def install_and_guard(*args: object, **kwargs: object) -> object:
        result = original_install(*args, **kwargs)
        _apply_magazine_display_bridge()
        return result

    install_and_guard._ABA_MAGAZINE_DIRECT_BRIDGE = True  # type: ignore[attr-defined]
    polish.install = install_and_guard  # type: ignore[assignment]


_install_report_source_quality_guard()
_install_magazine_reload_bridge()
_install_magazine_polish_bridge()
_apply_magazine_display_bridge()

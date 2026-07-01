from __future__ import annotations

import builtins
import importlib
import os

# This file intentionally does not monkey-patch Streamlit widgets.
# Keep Streamlit widget behavior native. Runtime helpers here are limited to
# safe secret lookup and magazine-renderer repair after module reloads.


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


def _ci_enabled() -> bool:
    return os.getenv("CI", "").lower() in {"1", "true", "yes"}


def _decimal_odds_text(value: object) -> str | None:
    raw = str(value or "").replace("−", "-").replace("–", "-").replace("—", "-")
    raw = raw.replace(",", "").strip()
    if not raw:
        return None
    try:
        num = float(raw)
    except Exception:
        return None
    if num <= -100:
        decimal = 1.0 + 100.0 / abs(num)
    elif num >= 100:
        decimal = 1.0 + num / 100.0
    elif num > 1:
        decimal = num
    else:
        return None
    return f"{decimal:.2f}".rstrip("0").rstrip(".")


def _apply_magazine_display_bridge(module: object | None = None) -> None:
    if _ci_enabled():
        return
    try:
        if module is None:
            import autonomous_betting_agent.magazine_book_export as module  # type: ignore[no-redef]
        original_fmt = getattr(module, "_fmt", None)
        if callable(original_fmt) and not getattr(original_fmt, "_ABA_SITE_DECIMAL_ODDS", False):
            def fmt_decimal_first(value: object, kind: str = "") -> str:
                if kind == "odds":
                    decimal = _decimal_odds_text(value)
                    if decimal:
                        return decimal
                return original_fmt(value, kind)

            fmt_decimal_first._ABA_SITE_DECIMAL_ODDS = True  # type: ignore[attr-defined]
            setattr(module, "_fmt", fmt_decimal_first)

        original_cells = getattr(module, "magazine_metric_cells", None)
        if callable(original_cells) and not getattr(original_cells, "_ABA_SITE_GOLD_WATCHLIST", False):
            def metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str):
                cells = list(original_cells(odds, conf, edge, ev, units, risk))
                gold = (241, 184, 45)
                fixed = []
                for label, value, color, x, width in cells:
                    if str(label).upper() == "RISK" and any(token in str(risk).lower() for token in ("fallback", "verify", "watch", "volume")):
                        color = gold
                    fixed.append((label, value, color, x, width))
                return fixed

            metric_cells._ABA_SITE_GOLD_WATCHLIST = True  # type: ignore[attr-defined]
            setattr(module, "magazine_metric_cells", metric_cells)

        try:
            from autonomous_betting_agent.magazine_display_guard import install as install_display_guard
            install_display_guard(module)
        except Exception:
            pass
    except Exception:
        pass


def _install_magazine_reload_bridge() -> None:
    if _ci_enabled() or getattr(importlib.reload, "_ABA_MAGAZINE_DISPLAY_BRIDGE", False):
        return
    original_reload = getattr(importlib, "_aba_original_reload", importlib.reload)
    setattr(importlib, "_aba_original_reload", original_reload)

    def reload_with_magazine_bridge(module: object) -> object:
        reloaded = original_reload(module)
        if getattr(reloaded, "__name__", "") == "autonomous_betting_agent.magazine_book_export":
            _apply_magazine_display_bridge(reloaded)
        return reloaded

    reload_with_magazine_bridge._ABA_MAGAZINE_DISPLAY_BRIDGE = True  # type: ignore[attr-defined]
    importlib.reload = reload_with_magazine_bridge


def _install_magazine_polish_bridge() -> None:
    if _ci_enabled():
        return
    try:
        import autonomous_betting_agent.magazine_report_polish_patch as polish
    except Exception:
        return
    original_install = getattr(polish, "install", None)
    if not callable(original_install) or getattr(original_install, "_ABA_MAGAZINE_DISPLAY_BRIDGE", False):
        return

    def install_and_guard(*args: object, **kwargs: object) -> object:
        result = original_install(*args, **kwargs)
        _apply_magazine_display_bridge()
        return result

    install_and_guard._ABA_MAGAZINE_DISPLAY_BRIDGE = True  # type: ignore[attr-defined]
    polish.install = install_and_guard  # type: ignore[assignment]


_install_magazine_reload_bridge()
_install_magazine_polish_bridge()
_apply_magazine_display_bridge()

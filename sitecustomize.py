from __future__ import annotations

import builtins
import importlib
import os

# This file intentionally keeps Streamlit widgets native except for one narrow
# display-only Odds Lock Pro count bridge. The bridge never writes ledgers.


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


def _install_odds_lock_count_bridge() -> None:
    if _runtime_disabled():
        return
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    original_metric = getattr(DeltaGenerator, "metric", None)
    if not callable(original_metric) or getattr(original_metric, "_ABA_ODDS_LOCK_COUNT_BRIDGE", False):
        return

    def is_zero(value: object) -> bool:
        try:
            return float(str(value or "0").replace(",", "").strip()) == 0.0
        except Exception:
            return str(value or "").strip() in {"", "0"}

    def truthy(value: object) -> bool:
        return str(value or "").strip().lower() in {"true", "1", "yes", "y", "pass", "ok"}

    def saved_counts() -> dict[str, int]:
        try:
            module = importlib.import_module("autonomous_" + "betting_agent.commercial_platform_tools")
            workspace = module.normalize_workspace_id(st.session_state.get("aba_test_window_id", "test_01"))
            ledger = module.load_persistent_ledger(workspace_id=workspace)
            if ledger is None or ledger.empty:
                return {"official": 0, "research": 0}
            official = research = 0
            for row in ledger.to_dict("records"):
                ledger_type = str(row.get("ledger_type") or row.get("proof_type") or "").strip().lower()
                public_confidence = str(row.get("public_confidence") or "").strip().lower()
                if truthy(row.get("official_ev_pick")) or ledger_type == "official_plus_ev_future_only":
                    official += 1
                elif ledger_type == "research_test_future_only" or "research" in public_confidence:
                    research += 1
            return {"official": official, "research": research}
        except Exception:
            return {"official": 0, "research": 0}

    def metric_bridge(self: object, label: object, value: object, *args: object, **kwargs: object) -> object:
        try:
            text = str(label or "").strip().lower()
            if is_zero(value) and text in {"official +ev", "oficial +ev", "research/test", "investigacion/prueba", "investigación/prueba"}:
                counts = saved_counts()
                if text in {"official +ev", "oficial +ev"} and counts["official"] > 0:
                    value = counts["official"]
                elif counts["research"] > 0:
                    value = counts["research"]
        except Exception:
            pass
        return original_metric(self, label, value, *args, **kwargs)

    metric_bridge._ABA_ODDS_LOCK_COUNT_BRIDGE = True  # type: ignore[attr-defined]
    DeltaGenerator.metric = metric_bridge  # type: ignore[assignment]


_install_report_source_quality_guard()
_install_magazine_reload_bridge()
_install_magazine_polish_bridge()
_install_odds_lock_count_bridge()
_apply_magazine_display_bridge()

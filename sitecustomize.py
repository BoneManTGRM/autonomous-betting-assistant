from __future__ import annotations

import builtins
import importlib
import os

# This file intentionally does not monkey-patch Streamlit widgets.


def get_secret(*names: str) -> str:
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if st is not None:
            try:
                value = str(st.secrets.get(name, '') or '').strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret


def _runtime_disabled() -> bool:
    return os.getenv('GITHUB_ACTIONS', '').lower() in {'1', 'true', 'yes'} or os.getenv('ABA_DISABLE_RUNTIME_PATCHES', '').lower() in {'1', 'true', 'yes'}


def _apply_balldontlie_bridge(module: object | None = None) -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.balldontlie_integration import install
        install(module)
    except Exception:
        pass


def _install_source_hook() -> None:
    if _runtime_disabled():
        return
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st, '_ABA_SOURCE_HOOK', False):
        return
    old_subheader = st.subheader
    old_caption = st.caption

    def caption(body, *args, **kwargs):
        text = str(body or '')
        if text.startswith('App version: pro-predictor-v23'):
            body = 'App version: pro-predictor-v24-balldontlie-api-registry'
        return old_caption(body, *args, **kwargs)

    def subheader(body, *args, **kwargs):
        result = old_subheader(body, *args, **kwargs)
        if str(body or '').strip().lower() in {'api sources', 'fuentes api'} and not st.session_state.get('_aba_bdl_ui'):
            st.session_state['_aba_bdl_ui'] = True
            key = get_secret('BALLDONTLIE_API_KEY', 'BDL_API_KEY', 'BALLDONTLIE_KEY')
            col, _, _ = st.columns(3)
            col.metric("Ball Don't Lie", 'Enabled' if key else 'Missing')
        return result

    st.caption = caption
    st.subheader = subheader
    st._ABA_SOURCE_HOOK = True


def _apply_parlay_intelligence_bridge(module: object | None = None) -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.parlay_intelligence_patch import install
        install(module)
    except Exception:
        pass


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
    _apply_balldontlie_bridge(module)
    _apply_parlay_intelligence_bridge(module)


def _install_report_source_quality_guard() -> None:
    if _runtime_disabled():
        return
    try:
        from autonomous_betting_agent.report_source_quality_guard import install
        install()
    except Exception:
        pass


def _install_magazine_reload_bridge() -> None:
    if _runtime_disabled() or getattr(importlib.reload, '_ABA_MAGAZINE_DIRECT_BRIDGE', False):
        return
    original_reload = getattr(importlib, '_aba_original_reload', importlib.reload)
    setattr(importlib, '_aba_original_reload', original_reload)

    def reload_with_magazine_bridge(module: object) -> object:
        reloaded = original_reload(module)
        if getattr(reloaded, '__name__', '') == 'autonomous_betting_agent.magazine_book_export':
            _apply_magazine_display_bridge(reloaded)
        return reloaded

    reload_with_magazine_bridge._ABA_MAGAZINE_DIRECT_BRIDGE = True
    importlib.reload = reload_with_magazine_bridge


def _install_magazine_polish_bridge() -> None:
    if _runtime_disabled():
        return
    try:
        import autonomous_betting_agent.magazine_report_polish_patch as polish
    except Exception:
        return
    original_install = getattr(polish, 'install', None)
    if not callable(original_install) or getattr(original_install, '_ABA_MAGAZINE_DIRECT_BRIDGE', False):
        return

    def install_and_guard(*args: object, **kwargs: object) -> object:
        result = original_install(*args, **kwargs)
        _apply_magazine_display_bridge()
        return result

    install_and_guard._ABA_MAGAZINE_DIRECT_BRIDGE = True
    polish.install = install_and_guard


_install_report_source_quality_guard()
_install_magazine_reload_bridge()
_install_magazine_polish_bridge()
_install_source_hook()
_apply_magazine_display_bridge()

from __future__ import annotations

import builtins
import inspect
import os


def get_secret(*names: str) -> str:
    """Read a Streamlit secret or environment variable by one of several names.

    Some older pages call get_secret directly. Registering this helper in
    builtins keeps those pages working without duplicating the same function in
    every Streamlit page.
    """
    try:
        import streamlit as st
    except Exception:
        st = None  # type: ignore[assignment]
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, "")).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


builtins.get_secret = get_secret


def _called_from_pro_predictor() -> bool:
    try:
        return any(str(frame.filename).replace("\\", "/").endswith("pages/pro_predictor.py") for frame in inspect.stack())
    except Exception:
        return False


def _install_pro_predictor_odds_breakdown() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st, "_aba_pro_predictor_odds_breakdown_installed", False):
        return
    st._aba_pro_predictor_odds_breakdown_installed = True
    real_info = st.info
    real_code = st.code

    def render_once() -> None:
        if st.session_state.get("_aba_pro_predictor_odds_breakdown_rendered"):
            return
        st.session_state["_aba_pro_predictor_odds_breakdown_rendered"] = True
        try:
            from autonomous_betting_agent.odds_breakdown import render_odds_breakdown_section

            render_odds_breakdown_section("pro_predictor")
        except Exception as exc:
            real_info(f"What Are the Odds section could not load: {exc}")

    def patched_info(body, *args, **kwargs):
        result = real_info(body, *args, **kwargs)
        text = str(body)
        if _called_from_pro_predictor() and ("Enter API keys" in text or "Ingresa las claves" in text):
            render_once()
        return result

    def patched_code(body, *args, **kwargs):
        result = real_code(body, *args, **kwargs)
        if _called_from_pro_predictor():
            render_once()
        return result

    st.info = patched_info
    st.code = patched_code


# Python imports sitecustomize automatically at interpreter startup when this
# repository is on sys.path. Importing the package installs the global Streamlit
# language/sidebar/report translator before any page renders.
try:
    import autonomous_betting_agent  # noqa: F401
except Exception:
    # Keep app startup safe even if a non-Streamlit command imports Python with a
    # partially installed environment.
    pass

_install_pro_predictor_odds_breakdown()

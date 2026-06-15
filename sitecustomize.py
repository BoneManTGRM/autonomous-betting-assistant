from __future__ import annotations

import builtins
import inspect
import os
from typing import Any


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

# Python imports sitecustomize automatically at interpreter startup when this
# repository is on sys.path. Importing the package installs the global Streamlit
# language/sidebar/report translator before any page renders.
try:
    import autonomous_betting_agent  # noqa: F401
except Exception:
    # Keep app startup safe even if a non-Streamlit command imports Python with a
    # partially installed environment.
    pass


def _called_from_page(page_name: str) -> bool:
    try:
        suffix = f"pages/{page_name}".replace("\\", "/")
        return any(str(frame.filename).replace("\\", "/").endswith(suffix) for frame in inspect.stack())
    except Exception:
        return False


def _called_from_pro_predictor() -> bool:
    return _called_from_page("pro_predictor.py")


def _called_from_learning_memory() -> bool:
    return _called_from_page("learn_memory.py")


def _looks_like_predictor_report(data: Any) -> bool:
    try:
        import pandas as pd
    except Exception:
        return False
    if not isinstance(data, pd.DataFrame) or data.empty:
        return False
    keys = {str(col).strip().lower().replace(" ", "_") for col in data.columns}
    return bool(
        {"event", "prediction", "best_price"}.issubset(keys)
        or {"evento", "pronostico", "mejor_cuota"}.issubset(keys)
        or "target_70_mode" in keys
        or "modo_objetivo_70" in keys
    )


def _install_page_helpers() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, "_aba_page_helpers_installed", False):
        return
    st._aba_page_helpers_installed = True
    real_st_dataframe = st.dataframe
    real_dg_dataframe = DeltaGenerator.dataframe
    real_subheader = st.subheader

    def capture(data: Any) -> None:
        if _called_from_pro_predictor() and _looks_like_predictor_report(data):
            try:
                st.session_state["_aba_pro_predictor_latest_report"] = data.copy()
            except Exception:
                pass

    def patched_st_dataframe(data: Any = None, *args: Any, **kwargs: Any) -> Any:
        capture(data)
        return real_st_dataframe(data, *args, **kwargs)

    def patched_dg_dataframe(self: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        capture(data)
        return real_dg_dataframe(self, data, *args, **kwargs)

    def render_learning_reader_once() -> None:
        if st.session_state.get("_aba_learning_report_reader_rendered"):
            return
        st.session_state["_aba_learning_report_reader_rendered"] = True
        try:
            from autonomous_betting_agent.learning_report_reader import render_learning_report_reader

            render_learning_report_reader()
        except Exception as exc:
            real_subheader(f"Odds report reader could not load: {exc}")

    def patched_subheader(body: Any, *args: Any, **kwargs: Any) -> Any:
        result = real_subheader(body, *args, **kwargs)
        text = str(body)
        if _called_from_learning_memory() and ("Train from finished games" in text or "Entrenar con partidos terminados" in text):
            render_learning_reader_once()
        return result

    st.dataframe = patched_st_dataframe
    DeltaGenerator.dataframe = patched_dg_dataframe
    st.subheader = patched_subheader


_install_page_helpers()

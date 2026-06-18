from __future__ import annotations

from typing import Any

import streamlit as st

APP_NAME = "ABA Signal Pro"
APP_TAGLINE = "Powered by Reparodynamics"

st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)


def _is_numeric_value(value: Any) -> bool:
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def _slider_as_number_input(target: Any, original_slider: Any, *args: Any, **kwargs: Any) -> Any:
    original_kwargs = dict(kwargs)
    try:
        if args:
            label = args[0]
            rest = list(args[1:])
        else:
            label = kwargs.pop("label")
            rest = []
        ordered = [
            "min_value", "max_value", "value", "step", "format", "key", "help",
            "on_change", "args", "kwargs", "disabled", "label_visibility",
        ]
        params: dict[str, Any] = {}
        for name in ordered:
            if rest:
                params[name] = rest.pop(0)
            elif name in kwargs:
                params[name] = kwargs.pop(name)
        if rest:
            return original_slider(*args, **original_kwargs)
        min_value = params.get("min_value")
        max_value = params.get("max_value")
        value = params.get("value")
        step = params.get("step")
        if isinstance(value, (list, tuple)) or not all(_is_numeric_value(item) for item in (min_value, max_value, value, step)):
            return original_slider(*args, **original_kwargs)
        if value is None:
            value = min_value if min_value is not None else 0.0
        number_kwargs: dict[str, Any] = dict(kwargs)
        for name in ("min_value", "max_value", "step", "format", "key", "help", "on_change", "args", "kwargs"):
            if name in params and params[name] is not None:
                number_kwargs[name] = params[name]
        if "disabled" in params:
            number_kwargs["disabled"] = params["disabled"]
        if "label_visibility" in params:
            number_kwargs["label_visibility"] = params["label_visibility"]
        number_kwargs["value"] = value
        return target.number_input(label, **number_kwargs)
    except Exception:
        return original_slider(*args, **original_kwargs)


if not getattr(st, "_aba_numeric_slider_patch", False):
    st._aba_original_slider = st.slider

    def _st_slider_as_number_input(*args: Any, **kwargs: Any) -> Any:
        return _slider_as_number_input(st, st._aba_original_slider, *args, **kwargs)

    st.slider = _st_slider_as_number_input
    st._aba_numeric_slider_patch = True

try:
    from streamlit.delta_generator import DeltaGenerator

    if not getattr(DeltaGenerator, "_aba_numeric_slider_patch", False):
        DeltaGenerator._aba_original_slider = DeltaGenerator.slider

        def _delta_slider_as_number_input(self: Any, *args: Any, **kwargs: Any) -> Any:
            return _slider_as_number_input(self, DeltaGenerator._aba_original_slider.__get__(self, DeltaGenerator), *args, **kwargs)

        DeltaGenerator.slider = _delta_slider_as_number_input
        DeltaGenerator._aba_numeric_slider_patch = True
except Exception:
    pass

LANG_VALUE = st.session_state.get("global_language", st.session_state.get("pro_predictor_language", "English"))
LANG = "es" if LANG_VALUE == "Español" else "en"

NAV_LABELS = {
    "en": {
        "signal_board": "Signal Board",
        "pro_predictor": "Pro Predictor",
        "simulation_lab": "Simulation Lab",
        "threshold_optimizer": "Threshold Optimizer",
        "what_are_the_odds": "What Are the Odds",
        "odds_lock_pro": "Odds Lock Pro",
        "public_proof_dashboard": "Public Proof Dashboard",
        "learning_memory": "Learning Memory",
        "reset_lock_file": "Reset Lock File",
    },
    "es": {
        "signal_board": "Signal Board",
        "pro_predictor": "Predictor Pro",
        "simulation_lab": "Laboratorio de Simulación",
        "threshold_optimizer": "Optimizador de Umbral",
        "what_are_the_odds": "Qué Probabilidades Hay",
        "odds_lock_pro": "Odds Lock Pro",
        "public_proof_dashboard": "Dashboard Público de Prueba",
        "learning_memory": "Memoria de Aprendizaje",
        "reset_lock_file": "Reiniciar Archivo de Bloqueo",
    },
}


def nav_text(key: str) -> str:
    return NAV_LABELS[LANG].get(key, NAV_LABELS["en"].get(key, key))


st.sidebar.markdown("### :green[ABA] Signal :red[Pro]")
st.sidebar.caption(APP_TAGLINE)
st.sidebar.markdown("---")

PAGES = [
    st.Page("pages/signal_board.py", title=nav_text("signal_board")),
    st.Page("pages/pro_predictor.py", title=nav_text("pro_predictor")),
    st.Page("pages/simulation_lab.py", title=nav_text("simulation_lab")),
    st.Page("pages/threshold_optimizer.py", title=nav_text("threshold_optimizer")),
    st.Page("pages/what_are_the_odds.py", title=nav_text("what_are_the_odds")),
    st.Page("pages/odds_lock_pro.py", title=nav_text("odds_lock_pro")),
    st.Page("pages/public_proof_dashboard.py", title=nav_text("public_proof_dashboard")),
    st.Page("pages/learn_memory.py", title=nav_text("learning_memory")),
    st.Page("pages/reset_lock_file.py", title=nav_text("reset_lock_file")),
]

current_page = st.navigation(PAGES, position="sidebar", expanded=True)


def _ignore_late_page_config(*args: Any, **kwargs: Any) -> None:
    return None


st.set_page_config = _ignore_late_page_config
current_page.run()

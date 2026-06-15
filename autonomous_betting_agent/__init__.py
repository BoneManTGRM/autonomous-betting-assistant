"""Autonomous Betting Agent.

A standalone, research-only sports analytics agent derived from the ARA/TGRM
architecture. It estimates probabilities, explains evidence, tracks uncertainty,
learns probability calibration from graded results, tracks edge/profit/CLV, and
supports backtesting.
"""

from __future__ import annotations

from typing import Any

from .learning import GradedPrediction, ProbabilityCalibrator, fit_probability_calibrator, parse_graded_csv
from .models import EventResearchInput, PredictionResult, TeamSnapshot
from .researcher import AutonomousBettingAgent
from .tgrm import TGRMLoop
from .tracking import PredictionLedgerRow, SelectionDecision, SelectionPolicy, TrackingReport, choose_decision, summarize_tracking


def _install_bilingual_sidebar() -> None:
    """Install a Streamlit sidebar patch when the package is imported by app pages.

    Streamlit Cloud does not reliably import sitecustomize in every deployment.
    Installing here is more reliable because every page imports at least one
    autonomous_betting_agent module before rendering its UI.
    """
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    if getattr(st, "_aba_bilingual_sidebar_installed", False):
        return
    st._aba_bilingual_sidebar_installed = True

    tools: tuple[tuple[str, str, str], ...] = (
        ("Pro Predictor", "Predictor Pro", "pages/pro_predictor.py"),
        ("Learning Memory", "Memoria de Aprendizaje", "pages/learn_memory.py"),
        ("Pro Intelligence Scanner", "Escáner Pro de Inteligencia", "pages/pro_intelligence_scanner.py"),
        ("Weather Intelligence", "Inteligencia de Clima", "pages/weather_intelligence.py"),
        ("Accuracy Tracker", "Rastreador de Precisión", "pages/accuracy_tracker.py"),
        ("Live Market Scanner", "Escáner de Mercado en Vivo", "pages/live_scanner.py"),
        ("US Pro Team Market Finder", "Buscador de Equipos Pro USA", "pages/us_pro_team_market_finder.py"),
        ("Mexico Team Market Finder", "Buscador de Equipos Mexicanos", "pages/mexico_team_market_finder.py"),
        ("College Team Market Finder", "Buscador de Equipos Universitarios", "pages/college_team_market_finder.py"),
        ("Combat Sports Fighter Finder", "Buscador de Peleadores", "pages/combat_sports_fighter_finder.py"),
        ("NBA Playoffs Predictor", "Predictor de Playoffs NBA", "pages/nba_playoffs_predictor.py"),
        ("Self Learning Engine", "Motor de Aprendizaje", "pages/self_learning_engine.py"),
    )
    notes_en = (
        "Primary tools: Pro Predictor, Learning Memory, Pro Intelligence Scanner, Weather Intelligence.",
        "Likely overlap: Live Market Scanner is a simpler version of Pro Intelligence Scanner.",
        "Likely overlap: Self Learning Engine is older than Learning Memory.",
        "Specialized tools: US, Mexico, College, Combat, and NBA pages are focused finders, not full replacements for Pro Predictor.",
    )
    notes_es = (
        "Herramientas principales: Predictor Pro, Memoria de Aprendizaje, Escáner Pro de Inteligencia, Inteligencia de Clima.",
        "Posible duplicado: Escáner de Mercado en Vivo es una versión más simple del Escáner Pro de Inteligencia.",
        "Posible duplicado: Motor de Aprendizaje es anterior a Memoria de Aprendizaje.",
        "Herramientas especializadas: las páginas USA, México, Universitario, Combate y NBA son buscadores enfocados, no reemplazos completos del Predictor Pro.",
    )

    def language_value() -> str:
        return str(st.session_state.get("global_language", "English"))

    def render_nav() -> None:
        if st.session_state.get("_bilingual_nav_rendered"):
            return
        st.session_state["_bilingual_nav_rendered"] = True
        with st.sidebar:
            st.markdown("---")
            st.markdown("### Tools / Herramientas")
            for english, spanish, path in tools:
                try:
                    st.page_link(path, label=f"{english} / {spanish}")
                except Exception:
                    st.caption(f"{english} / {spanish}")
            st.markdown("---")
            st.markdown("### Tool cleanup / Limpieza")
            for note in (notes_es if language_value() == "Español" else notes_en):
                st.caption(note)

    real_set_page_config = st.set_page_config
    real_st_selectbox = st.selectbox
    real_dg_selectbox = DeltaGenerator.selectbox

    def patched_set_page_config(*args: Any, **kwargs: Any) -> Any:
        result = real_set_page_config(*args, **kwargs)
        render_nav()
        return result

    def language_selectbox(label: Any, options: Any, args: tuple[Any, ...], kwargs: dict[str, Any], original: Any, target: Any = None) -> Any:
        label_text = str(label or "").lower()
        is_language = "language" in label_text or "idioma" in label_text or "translate page" in label_text
        opts = list(options)
        if is_language and "English" in opts and "Español" in opts:
            kwargs = dict(kwargs)
            kwargs.setdefault("key", "global_language")
            current = language_value()
            if "index" not in kwargs and current in opts:
                kwargs["index"] = opts.index(current)
            if target is None:
                value = st.sidebar.selectbox("Language / Idioma", opts, *args, **kwargs)
            else:
                value = original(target, "Language / Idioma", opts, *args, **kwargs)
            st.session_state["global_language"] = value
            render_nav()
            return value
        if target is None:
            return original(label, options, *args, **kwargs)
        return original(target, label, options, *args, **kwargs)

    def patched_st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return language_selectbox(label, options, args, kwargs, real_st_selectbox)

    def patched_dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return language_selectbox(label, options, args, kwargs, real_dg_selectbox, target=self)

    st.set_page_config = patched_set_page_config
    st.selectbox = patched_st_selectbox
    DeltaGenerator.selectbox = patched_dg_selectbox


_install_bilingual_sidebar()

__all__ = [
    "AutonomousBettingAgent",
    "EventResearchInput",
    "GradedPrediction",
    "PredictionLedgerRow",
    "PredictionResult",
    "ProbabilityCalibrator",
    "SelectionDecision",
    "SelectionPolicy",
    "TeamSnapshot",
    "TGRMLoop",
    "TrackingReport",
    "choose_decision",
    "fit_probability_calibrator",
    "parse_graded_csv",
    "summarize_tracking",
]

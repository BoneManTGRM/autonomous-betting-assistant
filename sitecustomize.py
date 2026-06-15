from __future__ import annotations

from typing import Any

try:
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator
except Exception:  # pragma: no cover - app startup safety
    st = None  # type: ignore[assignment]
    DeltaGenerator = None  # type: ignore[assignment]


TOOLS: tuple[tuple[str, str, str], ...] = (
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

TOOL_NOTES_EN = (
    "Primary tools: Pro Predictor, Learning Memory, Pro Intelligence Scanner, Weather Intelligence.",
    "Likely overlap: Live Market Scanner is a simpler version of Pro Intelligence Scanner.",
    "Likely overlap: Self Learning Engine is older than Learning Memory.",
    "Specialized tools: US, Mexico, College, Combat, and NBA pages are focused finders, not full replacements for Pro Predictor.",
)

TOOL_NOTES_ES = (
    "Herramientas principales: Predictor Pro, Memoria de Aprendizaje, Escáner Pro de Inteligencia, Inteligencia de Clima.",
    "Posible duplicado: Escáner de Mercado en Vivo es una versión más simple del Escáner Pro de Inteligencia.",
    "Posible duplicado: Motor de Aprendizaje es anterior a Memoria de Aprendizaje.",
    "Herramientas especializadas: las páginas USA, México, Universitario, Combate y NBA son buscadores enfocados, no reemplazos completos del Predictor Pro.",
)


def _language_value() -> str:
    if st is None:
        return "English"
    return str(st.session_state.get("global_language", "English"))


def _render_bilingual_nav() -> None:
    if st is None:
        return
    if st.session_state.get("_bilingual_nav_rendered"):
        return
    st.session_state["_bilingual_nav_rendered"] = True
    lang = _language_value()
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Tools / Herramientas")
        for english, spanish, path in TOOLS:
            label = f"{english} / {spanish}"
            try:
                st.page_link(path, label=label)
            except Exception:
                st.caption(label)
        st.markdown("---")
        st.markdown("### Tool cleanup / Limpieza")
        for note in (TOOL_NOTES_ES if lang == "Español" else TOOL_NOTES_EN):
            st.caption(note)


def _language_selectbox(label: Any, options: Any, args: tuple[Any, ...], kwargs: dict[str, Any], original: Any, target: Any = None) -> Any:
    text = str(label or "").strip().lower()
    is_language = "language" in text or "idioma" in text or "translate page" in text
    if not is_language:
        return original(label, options, *args, **kwargs) if target is None else original(target, label, options, *args, **kwargs)

    opts = list(options)
    if "English" in opts and "Español" in opts:
        kwargs = dict(kwargs)
        kwargs.setdefault("key", "global_language")
        current = str(st.session_state.get("global_language", "English")) if st is not None else "English"
        if "index" not in kwargs and current in opts:
            kwargs["index"] = opts.index(current)
        if target is None:
            value = st.sidebar.selectbox("Language / Idioma", opts, *args, **kwargs)
        else:
            value = original(target, "Language / Idioma", opts, *args, **kwargs)
        if st is not None:
            st.session_state["global_language"] = value
        _render_bilingual_nav()
        return value

    return original(label, options, *args, **kwargs) if target is None else original(target, label, options, *args, **kwargs)


if st is not None and DeltaGenerator is not None:
    _real_set_page_config = st.set_page_config
    _real_st_selectbox = st.selectbox
    _real_dg_selectbox = DeltaGenerator.selectbox

    def _patched_set_page_config(*args: Any, **kwargs: Any) -> Any:
        result = _real_set_page_config(*args, **kwargs)
        _render_bilingual_nav()
        return result

    def _patched_st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return _language_selectbox(label, options, args, kwargs, _real_st_selectbox)

    def _patched_dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return _language_selectbox(label, options, args, kwargs, _real_dg_selectbox, target=self)

    st.set_page_config = _patched_set_page_config
    st.selectbox = _patched_st_selectbox
    DeltaGenerator.selectbox = _patched_dg_selectbox

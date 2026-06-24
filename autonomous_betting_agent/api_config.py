"""Optional external API configuration helpers.

Keys are optional. Missing keys keep the app in local CSV-only mode.
Secret values are never logged or returned by status helpers.
"""

from __future__ import annotations

import os
from typing import Any

_OPTIONAL_KEYS = {
    "api-football": "API_FOOTBALL_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "newsapi": "NEWSAPI_KEY",
}


def _streamlit_secret(name: str) -> str:
    try:
        import streamlit as st  # type: ignore

        value: Any = st.secrets.get(name, "")
        return str(value or "")
    except Exception:
        return ""


def _streamlit_session_secret(name: str) -> str:
    try:
        import streamlit as st  # type: ignore

        value: Any = st.session_state.get(name, "") or st.session_state.get(f"optional_{name}", "")
        return str(value or "")
    except Exception:
        return ""


def get_secret(name: str, default: str = "") -> str:
    """Return a key from Streamlit secrets, environment, or session state.

    Session state support lets the predictor page accept temporary test keys
    without requiring redeploying Streamlit secrets. Values are never printed.
    """
    value = _streamlit_secret(name) or os.getenv(name, "") or _streamlit_session_secret(name)
    return str(value or default)


def has_api_football() -> bool:
    return bool(get_secret("API_FOOTBALL_KEY"))


def has_perplexity() -> bool:
    return bool(get_secret("PERPLEXITY_API_KEY"))


def has_newsapi() -> bool:
    return bool(get_secret("NEWSAPI_KEY"))


def available_api_sources() -> list[str]:
    available = []
    if has_api_football():
        available.append("api-football")
    if has_perplexity():
        available.append("perplexity")
    if has_newsapi():
        available.append("newsapi")
    return available


def api_status() -> dict[str, str]:
    return {name: "available" if get_secret(key) else "missing key" for name, key in _OPTIONAL_KEYS.items()}

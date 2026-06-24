"""Optional source configuration helpers.

Reads optional keys from Streamlit secrets first, then environment variables.
The app must continue in local CSV mode when keys are missing.
"""

from __future__ import annotations

import os
from typing import Any

FOOTBALL_KEY_NAME = "API_FOOTBALL_KEY"
RESEARCH_KEY_NAME = "PERPLEXITY_API_KEY"
NEWS_KEY_NAME = "NEWSAPI_KEY"


def _secret_store() -> Any:
    try:
        import streamlit as st  # type: ignore
        return st.secrets
    except Exception:
        return {}


def get_secret(name: str, default: str = "") -> str:
    if not name:
        return default
    store = _secret_store()
    try:
        value = store.get(name, "") if hasattr(store, "get") else ""
    except Exception:
        value = ""
    if value:
        return str(value)
    return os.getenv(name, default) or default


def has_api_football() -> bool:
    return bool(get_secret(FOOTBALL_KEY_NAME))


def has_perplexity() -> bool:
    return bool(get_secret(RESEARCH_KEY_NAME))


def has_newsapi() -> bool:
    return bool(get_secret(NEWS_KEY_NAME))


def available_api_sources() -> dict[str, bool]:
    return {
        "api-football": has_api_football(),
        "perplexity": has_perplexity(),
        "newsapi": has_newsapi(),
    }


def status_rows() -> list[dict[str, str]]:
    return [
        {"source": "API-Football", "status": "available" if has_api_football() else "missing key"},
        {"source": "Perplexity", "status": "available" if has_perplexity() else "missing key"},
        {"source": "NewsAPI", "status": "available" if has_newsapi() else "missing key"},
    ]

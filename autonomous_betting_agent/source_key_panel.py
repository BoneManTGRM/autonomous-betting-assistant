"""Compact Streamlit source-key panel for optional context sources."""

from __future__ import annotations

from typing import Any

from .api_config import api_status, get_secret


def render_optional_context_source_panel(st: Any, *, expanded: bool = False) -> dict[str, str]:
    """Render compact optional context source inputs.

    Values are stored only in Streamlit session state for the current app session
    unless they are already present in Streamlit secrets or environment vars.
    """
    values: dict[str, str] = {}
    with st.expander("Optional context sources", expanded=expanded):
        st.caption("Optional enrichment for reports, cards, magazines, soccer context, and chain review. Local CSV mode still works without these.")
        cols = st.columns(3)
        sources = [
            ("API-Football", "API_FOOTBALL_KEY"),
            ("Perplexity", "PERPLEXITY_API_KEY"),
            ("NewsAPI", "NEWSAPI_KEY"),
        ]
        for col, (label, key) in zip(cols, sources):
            saved = get_secret(key)
            value = col.text_input(f"{label} key", type="password", placeholder="Loaded from secrets" if saved else "", key=f"optional_context_{key}").strip() or saved
            values[key] = value
            if value:
                st.session_state[key] = value
            col.metric(label, "Enabled" if value else "Missing")
        st.caption("These sources can add context warnings and notes, but they do not override model probability, odds value, EV, risk gates, or ledger results.")
    return values


def render_optional_context_status(st: Any) -> None:
    status = api_status()
    st.caption("Optional context status: " + "; ".join(f"{name}: {state}" for name, state in status.items()))

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

try:
    from autonomous_betting_agent.memory_read_patch import install_memory_read_merge
except Exception:
    install_memory_read_merge = None  # type: ignore[assignment]

APP_NAME = "ARA Signal Pro"
APP_TAGLINE = "Powered by Reparodynamics"
APP_BUILD = "clean-sidebar-order-v2"
REPO_ROOT = Path(__file__).resolve().parent
REPO_MEMORY_PATH = REPO_ROOT / "data" / "ara_permanent_learning_memory.csv"

_REAL_SET_PAGE_CONFIG = st.set_page_config
_REAL_SIDEBAR_RADIO = st.sidebar.radio
_REAL_SIDEBAR_SELECTBOX = st.sidebar.selectbox
_REAL_DG_RADIO = getattr(DeltaGenerator, "radio", None)
_REAL_DG_SELECTBOX = DeltaGenerator.selectbox

_REAL_SET_PAGE_CONFIG(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit pages inside /pages also call set_page_config. The shell owns page config.
st.set_page_config = lambda *args, **kwargs: None

CORE_PAGES = [
    st.Page("pages/pro_predictor.py", title="Pro Predictor"),
    st.Page("pages/ultra80_profit_mode.py", title="Ultra 70 Profit Mode"),
    st.Page("pages/simulation_lab.py", title="Simulation Lab"),
    st.Page("pages/threshold_optimizer.py", title="Threshold Optimizer"),
    st.Page("pages/what_are_the_odds.py", title="What Are the Odds"),
    st.Page("pages/odds_lock_pro.py", title="Odds Lock Pro"),
    st.Page("pages/public_proof_dashboard.py", title="Public Proof Dashboard"),
    st.Page("pages/learn_memory.py", title="Learning Memory"),
    st.Page("pages/reset_lock_file.py", title="Reset Lock File"),
]

TOOL_LINKS = [
    ("pages/pro_predictor.py", "Pro Predictor"),
    ("pages/ultra80_profit_mode.py", "Ultra 70 Profit Mode"),
    ("pages/simulation_lab.py", "Simulation Lab"),
    ("pages/threshold_optimizer.py", "Threshold Optimizer"),
    ("pages/what_are_the_odds.py", "What Are the Odds"),
    ("pages/odds_lock_pro.py", "Odds Lock Pro"),
    ("pages/public_proof_dashboard.py", "Public Proof Dashboard"),
    ("pages/learn_memory.py", "Learning Memory"),
    ("pages/reset_lock_file.py", "Reset Lock File"),
]

LANGUAGE_KEYS = (
    "global_language",
    "app_language",
    "simulation_lab_language",
    "pro_predictor_language",
    "ultra80_profit_mode_language",
    "odds_lock_pro_language",
    "public_proof_dashboard_language",
    "reset_lock_file_language",
    "learn_memory_language",
    "learning_memory_language",
    "threshold_optimizer_language",
    "what_are_the_odds_language",
)

WORKFLOW_TEXT = "Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory."
WORKFLOW_DETAIL = "Odds Lock Pro timestamps locked picks; Public Proof Dashboard shows ROI and results."

CSS = """
<style>
[data-testid="collapsedControl"] { z-index: 999999 !important; }
@media (max-width: 900px) {
    section[data-testid="stSidebar"] {
        width: min(86vw, 360px) !important;
        min-width: min(86vw, 360px) !important;
        max-width: min(86vw, 360px) !important;
        box-shadow: 0 0 0 9999px rgba(0,0,0,.32) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: .75rem !important;
        padding-left: .9rem !important;
        padding-right: .9rem !important;
    }
    .block-container {
        padding-left: .85rem !important;
        padding-right: .85rem !important;
        max-width: 100vw !important;
    }
}
</style>
"""


def _normal_language(value: object) -> str:
    text = str(value or "").strip().lower()
    return "Español" if text.startswith("es") or "español" in text or "espanol" in text else "English"


def _is_language_widget(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    label_text = str(label or "").lower()
    return "English" in opts and "Español" in opts and ("language" in label_text or "idioma" in label_text)


def _sync_language(value: object) -> str:
    language = _normal_language(value)
    for key in LANGUAGE_KEYS:
        try:
            st.session_state[key] = language
        except Exception:
            pass
    return language


def install_report_branding() -> None:
    try:
        from autonomous_betting_agent import odds_lock_tools
    except Exception:
        return
    original_daily_report = getattr(odds_lock_tools, "daily_report", None)
    if not callable(original_daily_report) or getattr(original_daily_report, "_ara_brand_patched", False):
        return

    def branded_daily_report(*args: Any, **kwargs: Any) -> str:
        report = str(original_daily_report(*args, **kwargs) or "")
        if report.startswith(APP_NAME):
            return report
        return f"{APP_NAME}\n{APP_TAGLINE}\n\n{report}"

    branded_daily_report._ara_brand_patched = True  # type: ignore[attr-defined]
    odds_lock_tools.daily_report = branded_daily_report


def render_sidebar_after_language(language: object = "English") -> None:
    """Render custom sidebar immediately below the page-level language control."""
    if st.session_state.get("_ara_sidebar_after_language_rendered_v2"):
        return
    st.session_state["_ara_sidebar_after_language_rendered_v2"] = True
    current_language = _normal_language(language)
    tools_label = "Herramientas" if current_language == "Español" else "Pages"
    workflow_label = "Flujo" if current_language == "Español" else "Workflow"
    with st.sidebar:
        st.divider()
        st.markdown("### :green[ARA] Signal :red[Pro]")
        st.caption(APP_TAGLINE)
        st.divider()
        st.subheader(tools_label)
        for path, label in TOOL_LINKS:
            try:
                st.page_link(path, label=label)
            except Exception:
                st.caption(label)
        st.divider()
        st.subheader(workflow_label)
        st.caption(WORKFLOW_TEXT)
        st.caption(WORKFLOW_DETAIL)


def _language_radio(label: Any, options: Any, *args: Any, key: str | None = None, **kwargs: Any) -> Any:
    opts = list(options)
    current = st.session_state.get(key or "global_language", st.session_state.get("global_language", "English"))
    current = _normal_language(current)
    index = opts.index(current) if current in opts else 0
    value = _REAL_SIDEBAR_RADIO(
        "Language" if current == "English" else "Idioma",
        opts,
        index=index,
        key=key,
        horizontal=True,
    )
    language = _sync_language(value)
    render_sidebar_after_language(language)
    return value


def patched_sidebar_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_language_widget(label, options):
        return _language_radio(label, options, *args, **kwargs)
    return _REAL_SIDEBAR_SELECTBOX(label, options, *args, **kwargs)


def patched_sidebar_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_language_widget(label, options):
        value = _REAL_SIDEBAR_RADIO(label, options, *args, **kwargs)
        language = _sync_language(value)
        render_sidebar_after_language(language)
        return value
    return _REAL_SIDEBAR_RADIO(label, options, *args, **kwargs)


def patched_dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_language_widget(label, options):
        return _language_radio(label, options, *args, **kwargs)
    return _REAL_DG_SELECTBOX(self, label, options, *args, **kwargs)


def patched_dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_language_widget(label, options):
        value = _REAL_DG_RADIO(self, label, options, *args, **kwargs) if _REAL_DG_RADIO else _language_radio(label, options, *args, **kwargs)
        language = _sync_language(value)
        render_sidebar_after_language(language)
        return value
    return _REAL_DG_RADIO(self, label, options, *args, **kwargs) if _REAL_DG_RADIO else _REAL_SIDEBAR_RADIO(label, options, *args, **kwargs)


st.markdown(CSS, unsafe_allow_html=True)
st.sidebar.selectbox = patched_sidebar_selectbox
st.sidebar.radio = patched_sidebar_radio
DeltaGenerator.selectbox = patched_dg_selectbox
if _REAL_DG_RADIO is not None:
    DeltaGenerator.radio = patched_dg_radio

if install_memory_read_merge is not None:
    try:
        install_memory_read_merge(REPO_MEMORY_PATH)
    except Exception:
        pass
install_report_branding()

try:
    # Hidden routing prevents the giant automatic file list. Custom page links render below language.
    current_page = st.navigation(CORE_PAGES, position="hidden")
    current_page.run()
except AttributeError:
    import pages.pro_predictor  # noqa: F401,E402

# Fallback for pages that do not render a language widget.
render_sidebar_after_language(st.session_state.get("global_language", "English"))

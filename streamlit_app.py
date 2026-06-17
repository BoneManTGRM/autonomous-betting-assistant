from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

try:
    from autonomous_betting_agent.memory_read_patch import install_memory_read_merge
except Exception:
    install_memory_read_merge = None  # type: ignore[assignment]

APP_NAME = "ABA Signal Pro"
APP_TAGLINE = "Powered by Reparodynamics"
APP_BUILD = "clean-sidebar-order-v1"
REPO_ROOT = Path(__file__).resolve().parent
REPO_MEMORY_PATH = REPO_ROOT / "data" / "ara_permanent_learning_memory.csv"

_REAL_SET_PAGE_CONFIG = st.set_page_config

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


def install_report_branding() -> None:
    try:
        from autonomous_betting_agent import odds_lock_tools
    except Exception:
        return
    original_daily_report = getattr(odds_lock_tools, "daily_report", None)
    if not callable(original_daily_report) or getattr(original_daily_report, "_aba_brand_patched", False):
        return

    def branded_daily_report(*args: Any, **kwargs: Any) -> str:
        report = str(original_daily_report(*args, **kwargs) or "")
        if report.startswith(APP_NAME):
            return report
        return f"{APP_NAME}\n{APP_TAGLINE}\n\n{report}"

    branded_daily_report._aba_brand_patched = True  # type: ignore[attr-defined]
    odds_lock_tools.daily_report = branded_daily_report


def render_sidebar_after_language() -> None:
    """Render custom sidebar below the page-level language selector."""
    st.sidebar.divider()
    st.sidebar.markdown("### :green[ABA] Signal :red[Pro]")
    st.sidebar.caption(APP_TAGLINE)
    st.sidebar.divider()
    st.sidebar.subheader("Pages")
    for path, label in TOOL_LINKS:
        try:
            st.sidebar.page_link(path, label=label)
        except Exception:
            st.sidebar.caption(label)
    st.sidebar.divider()
    st.sidebar.subheader("Workflow")
    st.sidebar.caption(WORKFLOW_TEXT)
    st.sidebar.caption(WORKFLOW_DETAIL)


st.markdown(CSS, unsafe_allow_html=True)

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

render_sidebar_after_language()

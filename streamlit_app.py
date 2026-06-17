from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

try:
    from autonomous_betting_agent.memory_read_patch import install_memory_read_merge
except Exception:
    install_memory_read_merge = None  # type: ignore[assignment]

try:
    from autonomous_betting_agent.sidebar_tools import install_sidebar_tools
    install_sidebar_tools()
except Exception:
    pass

APP_NAME = 'ARA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
APP_BUILD = 'stable-sidebar-shell-v2-native-width'
REPO_ROOT = Path(__file__).resolve().parent
REPO_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_permanent_learning_memory.csv'

_REAL_SET_PAGE_CONFIG = st.set_page_config
_REAL_SET_PAGE_CONFIG(page_title=APP_NAME, layout='wide', initial_sidebar_state='collapsed')

# Child pages call set_page_config. The shell owns the page config to prevent conflicts.
st.set_page_config = lambda *args, **kwargs: None

CORE_PAGES = [
    st.Page('pages/pro_predictor.py', title='Pro Predictor'),
    st.Page('pages/ultra80_profit_mode.py', title='Ultra 70 Profit Mode'),
    st.Page('pages/simulation_lab.py', title='Simulation Lab'),
    st.Page('pages/threshold_optimizer.py', title='Threshold Optimizer'),
    st.Page('pages/what_are_the_odds.py', title='What Are the Odds'),
    st.Page('pages/odds_lock_pro.py', title='Odds Lock Pro'),
    st.Page('pages/public_proof_dashboard.py', title='Public Proof Dashboard'),
    st.Page('pages/learn_memory.py', title='Learning Memory'),
    st.Page('pages/reset_lock_file.py', title='Reset Lock File'),
]


def install_report_branding() -> None:
    try:
        from autonomous_betting_agent import odds_lock_tools
    except Exception:
        return
    original_daily_report = getattr(odds_lock_tools, 'daily_report', None)
    if not callable(original_daily_report) or getattr(original_daily_report, '_ara_brand_patched', False):
        return

    def branded_daily_report(*args: Any, **kwargs: Any) -> str:
        report = str(original_daily_report(*args, **kwargs) or '')
        if report.startswith(APP_NAME):
            return report
        return f'{APP_NAME}\n{APP_TAGLINE}\n\n{report}'

    branded_daily_report._ara_brand_patched = True  # type: ignore[attr-defined]
    odds_lock_tools.daily_report = branded_daily_report


if install_memory_read_merge is not None:
    try:
        install_memory_read_merge(REPO_MEMORY_PATH)
    except Exception:
        pass
install_report_branding()

try:
    # Hidden routing prevents Streamlit's automatic giant /pages file list.
    page = st.navigation(CORE_PAGES, position='hidden')
    page.run()
except AttributeError:
    import pages.pro_predictor  # noqa: F401,E402

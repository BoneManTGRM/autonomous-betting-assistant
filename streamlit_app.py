from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

try:
    from autonomous_betting_agent.memory_read_patch import install_memory_read_merge
except Exception:
    install_memory_read_merge = None  # type: ignore[assignment]

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
APP_BUILD = 'stable-native-sidebar-v1-signal-board'
REPO_ROOT = Path(__file__).resolve().parent
REPO_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_permanent_learning_memory.csv'


def mobile_safe_file_uploader(*args: Any, **kwargs: Any) -> Any:
    return st._aba_real_file_uploader(*args, **kwargs)


if not hasattr(st, '_aba_real_file_uploader'):
    st._aba_real_file_uploader = st.file_uploader
    st.file_uploader = mobile_safe_file_uploader

_REAL_SET_PAGE_CONFIG = st.set_page_config
_REAL_SET_PAGE_CONFIG(page_title=APP_NAME, layout='wide', initial_sidebar_state='expanded')

# Child pages call set_page_config. The shell owns page config to prevent conflicts.
st.set_page_config = lambda *args, **kwargs: None

st.sidebar.markdown('### :green[ABA] Signal :red[Pro]')
st.sidebar.caption(APP_TAGLINE)
st.sidebar.markdown('---')

CORE_PAGES = [
    st.Page('pages/signal_board.py', title='Signal Board'),
    st.Page('pages/pro_predictor.py', title='Pro Predictor'),
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
    page = st.navigation(CORE_PAGES, position='sidebar', expanded=True)
    page.run()
except AttributeError:
    import pages.pro_predictor  # noqa: F401,E402

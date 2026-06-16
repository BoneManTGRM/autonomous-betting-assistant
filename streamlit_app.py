from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from autonomous_betting_agent.memory_read_patch import install_memory_read_merge

_REAL_FILE_UPLOADER = st.file_uploader
_REAL_ST_NUMBER_INPUT = st.number_input
_REAL_ST_SLIDER = st.slider
_REAL_ST_TOGGLE = st.toggle
_REAL_DG_NUMBER_INPUT = DeltaGenerator.number_input
_REAL_DG_SLIDER = DeltaGenerator.slider
_REAL_DG_TOGGLE = DeltaGenerator.toggle

REPO_MEMORY_PATH = Path(__file__).resolve().parent / "data" / "ara_permanent_learning_memory.csv"

DEFAULT_NUMBER_INPUT_VALUES = {
    "max feeds": 50,
    "max events per feed": 35,
    "minimum books": 4,
    "70-mode minimum books": 4,
    "70-mode minimum reliability": 90.0,
    "70-mode minimum api coverage": 0.66,
}

DEFAULT_SLIDER_VALUES = {
    "minimum reliability": 90.0,
}

DEFAULT_TOGGLE_VALUES = {
    "require all configured apis": False,
}

CORE_PAGES = [
    st.Page("pages/scanner_pro.py", title="Scanner Pro"),
    st.Page("pages/pro_predictor.py", title="Pro Predictor"),
    st.Page("pages/ultra80_profit_mode.py", title="Ultra 80 Profit Mode"),
    st.Page("pages/simulation_lab.py", title="Simulation Lab"),
    st.Page("pages/threshold_optimizer.py", title="Threshold Optimizer"),
    st.Page("pages/what_are_the_odds.py", title="What Are the Odds"),
    st.Page("pages/odds_lock_pro.py", title="Odds Lock Pro"),
    st.Page("pages/public_proof_dashboard.py", title="Public Proof Dashboard"),
    st.Page("pages/reset_lock_file.py", title="Reset Lock File"),
    st.Page("pages/learn_memory.py", title="Learning Memory"),
]


def _label_key(label) -> str:
    return " ".join(str(label or "").lower().replace("%", "").replace("±", "").split())


def _apply_number_default(label, kwargs):
    key = _label_key(label)
    if key in DEFAULT_NUMBER_INPUT_VALUES:
        kwargs["value"] = DEFAULT_NUMBER_INPUT_VALUES[key]
    return kwargs


def _apply_slider_default(label, kwargs):
    key = _label_key(label)
    if key in DEFAULT_SLIDER_VALUES:
        kwargs["value"] = DEFAULT_SLIDER_VALUES[key]
    return kwargs


def _apply_toggle_default(label, kwargs):
    key = _label_key(label)
    if key in DEFAULT_TOGGLE_VALUES:
        kwargs["value"] = DEFAULT_TOGGLE_VALUES[key]
    return kwargs


def mobile_safe_file_uploader(label, *args, **kwargs):
    label_text = str(label).lower()
    if "memory" in label_text or "ara" in label_text:
        kwargs["type"] = None
        kwargs["accept_multiple_files"] = False
        if kwargs.get("key") == "ara_memory_csv_upload":
            kwargs["key"] = "ara_memory_mobile_safe_upload_v9"
        kwargs["help"] = "Accepts any file type. Choose your CSV file, or use the paste box."
    return _REAL_FILE_UPLOADER(label, *args, **kwargs)


def defaulted_st_number_input(label, *args, **kwargs):
    return _REAL_ST_NUMBER_INPUT(label, *args, **_apply_number_default(label, kwargs))


def defaulted_st_slider(label, *args, **kwargs):
    return _REAL_ST_SLIDER(label, *args, **_apply_slider_default(label, kwargs))


def defaulted_st_toggle(label, *args, **kwargs):
    return _REAL_ST_TOGGLE(label, *args, **_apply_toggle_default(label, kwargs))


def defaulted_dg_number_input(self, label, *args, **kwargs):
    return _REAL_DG_NUMBER_INPUT(self, label, *args, **_apply_number_default(label, kwargs))


def defaulted_dg_slider(self, label, *args, **kwargs):
    return _REAL_DG_SLIDER(self, label, *args, **_apply_slider_default(label, kwargs))


def defaulted_dg_toggle(self, label, *args, **kwargs):
    return _REAL_DG_TOGGLE(self, label, *args, **_apply_toggle_default(label, kwargs))


install_memory_read_merge(REPO_MEMORY_PATH)
st.file_uploader = mobile_safe_file_uploader
st.number_input = defaulted_st_number_input
st.slider = defaulted_st_slider
st.toggle = defaulted_st_toggle
DeltaGenerator.number_input = defaulted_dg_number_input
DeltaGenerator.slider = defaulted_dg_slider
DeltaGenerator.toggle = defaulted_dg_toggle

try:
    current_page = st.navigation(CORE_PAGES, position="sidebar")
    current_page.run()
except AttributeError:
    # Fallback for very old Streamlit versions. requirements.txt pins Streamlit
    # high enough for st.navigation, but this keeps local older installs usable.
    import pages.pro_predictor  # noqa: F401,E402

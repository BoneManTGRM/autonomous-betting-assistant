from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from autonomous_betting_agent.memory_read_patch import install_memory_read_merge

APP_NAME = "ABA Signal Pro"
APP_TAGLINE = "Powered by Reparodynamics"
APP_BUILD = "predictor-first-clean-sidebar-v4"
PREDICTOR_TOOL_NAME = "Pro Predictor"
BRANDED_REPORT_PREFIX = f"{APP_NAME}\n{APP_TAGLINE}"
REPO_ROOT = Path(__file__).resolve().parent
LOGO_PATH = REPO_ROOT / "assets" / "aba_signal_pro_logo.svg"

_REAL_SET_PAGE_CONFIG = st.set_page_config
_REAL_FILE_UPLOADER = st.file_uploader
_REAL_ST_CAPTION = st.caption
_REAL_ST_INFO = st.info
_REAL_ST_MARKDOWN = st.markdown
_REAL_ST_WRITE = st.write
_REAL_ST_NUMBER_INPUT = st.number_input
_REAL_ST_SLIDER = st.slider
_REAL_ST_TEXT_INPUT = st.text_input
_REAL_ST_TOGGLE = st.toggle
_REAL_DG_CAPTION = DeltaGenerator.caption
_REAL_DG_INFO = DeltaGenerator.info
_REAL_DG_MARKDOWN = DeltaGenerator.markdown
_REAL_DG_WRITE = DeltaGenerator.write
_REAL_DG_NUMBER_INPUT = DeltaGenerator.number_input
_REAL_DG_SELECTBOX = DeltaGenerator.selectbox
_REAL_DG_SLIDER = DeltaGenerator.slider
_REAL_DG_TEXT_INPUT = DeltaGenerator.text_input
_REAL_DG_TOGGLE = DeltaGenerator.toggle

_REAL_SET_PAGE_CONFIG(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)

REPO_MEMORY_PATH = REPO_ROOT / "data" / "ara_permanent_learning_memory.csv"

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

DEFAULT_TEXT_INPUT_VALUES = {
    "analyst / brand name": APP_NAME,
    "analista / marca": APP_NAME,
    "brand name": f"{APP_NAME} · {APP_TAGLINE}",
    "nombre de marca": f"{APP_NAME} · {APP_TAGLINE}",
    "card title": "ABA Signal Pro Proof Dashboard",
    "titulo de tarjeta": "Dashboard de Prueba ABA Signal Pro",
}

DEFAULT_TOGGLE_VALUES = {
    "require all configured apis": False,
}

CORE_PAGES = [
    st.Page("pages/pro_predictor.py", title=PREDICTOR_TOOL_NAME),
    st.Page("pages/ultra80_profit_mode.py", title="Ultra 70 Profit Mode"),
    st.Page("pages/simulation_lab.py", title="Simulation Lab"),
    st.Page("pages/threshold_optimizer.py", title="Threshold Optimizer"),
    st.Page("pages/what_are_the_odds.py", title="What Are the Odds"),
    st.Page("pages/odds_lock_pro.py", title="Odds Lock Pro"),
    st.Page("pages/public_proof_dashboard.py", title="Public Proof Dashboard"),
    st.Page("pages/reset_lock_file.py", title="Reset Lock File"),
    st.Page("pages/learn_memory.py", title="Learning Memory"),
]

TOOL_LINKS = [
    ("pages/pro_predictor.py", PREDICTOR_TOOL_NAME),
    ("pages/ultra80_profit_mode.py", "Ultra 70 Profit Mode"),
    ("pages/simulation_lab.py", "Simulation Lab"),
    ("pages/what_are_the_odds.py", "What Are the Odds"),
    ("pages/odds_lock_pro.py", "Odds Lock Pro"),
    ("pages/public_proof_dashboard.py", "Public Proof Dashboard"),
    ("pages/learn_memory.py", "Learning Memory"),
    ("pages/threshold_optimizer.py", "Threshold Optimizer"),
    ("pages/reset_lock_file.py", "Reset Lock File"),
]

WORKFLOW_TEXT = "Pro Predictor → Ultra 70 Profit Mode → Simulation Lab → Odds Lock Pro → Public Proof Dashboard → Learning Memory"


def safe_set_page_config(*args, **kwargs):
    """Ignore page-level config calls after the app shell has already configured Streamlit."""
    return None


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


def _slider_should_use_number_input(label) -> bool:
    key = _label_key(label)
    return "agent score" in key or "puntaje agente" in key


def _apply_text_default(label, kwargs):
    key = _label_key(label)
    if key in DEFAULT_TEXT_INPUT_VALUES:
        kwargs["value"] = DEFAULT_TEXT_INPUT_VALUES[key]
    return kwargs


def _apply_toggle_default(label, kwargs):
    key = _label_key(label)
    if key in DEFAULT_TOGGLE_VALUES:
        kwargs["value"] = DEFAULT_TOGGLE_VALUES[key]
    return kwargs


def _clean_ui_text(value):
    if not isinstance(value, str):
        return value
    return (
        value.replace("Scanner Pro / ", "")
        .replace(" / Scanner Pro", "")
        .replace("Scanner Pro → ", "")
        .replace("scanner/scanner", "predictor")
        .replace("scanner-only", "discovery-only")
        .replace("Scanner Pro", PREDICTOR_TOOL_NAME)
        .replace("scanner", "predictor")
        .replace("escáner", "predictor")
    )


def render_sidebar_brand() -> None:
    st.sidebar.markdown("### :green[ABA] Signal :red[Pro]")
    st.sidebar.caption(APP_TAGLINE)
    st.sidebar.caption(f"Build: {APP_BUILD}")
    st.sidebar.divider()
    st.sidebar.subheader("Tools")
    for path, label in TOOL_LINKS:
        try:
            st.sidebar.page_link(path, label=label)
        except Exception:
            st.sidebar.caption(label)
    st.sidebar.divider()
    st.sidebar.subheader("Workflow")
    st.sidebar.caption(WORKFLOW_TEXT)


def scrubbed_caption(body, *args, **kwargs):
    return _REAL_ST_CAPTION(_clean_ui_text(body), *args, **kwargs)


def scrubbed_info(body, *args, **kwargs):
    return _REAL_ST_INFO(_clean_ui_text(body), *args, **kwargs)


def scrubbed_markdown(body, *args, **kwargs):
    return _REAL_ST_MARKDOWN(_clean_ui_text(body), *args, **kwargs)


def scrubbed_write(*args, **kwargs):
    return _REAL_ST_WRITE(*[_clean_ui_text(arg) for arg in args], **kwargs)


def scrubbed_dg_caption(self, body, *args, **kwargs):
    return _REAL_DG_CAPTION(self, _clean_ui_text(body), *args, **kwargs)


def scrubbed_dg_info(self, body, *args, **kwargs):
    return _REAL_DG_INFO(self, _clean_ui_text(body), *args, **kwargs)


def scrubbed_dg_markdown(self, body, *args, **kwargs):
    return _REAL_DG_MARKDOWN(self, _clean_ui_text(body), *args, **kwargs)


def scrubbed_dg_write(self, *args, **kwargs):
    return _REAL_DG_WRITE(self, *[_clean_ui_text(arg) for arg in args], **kwargs)


def mobile_safe_file_uploader(label, *args, **kwargs):
    label_text = str(label).lower()
    if "memory" in label_text or "ara" in label_text:
        kwargs["type"] = None
        kwargs["accept_multiple_files"] = False
        if kwargs.get("key") == "ara_memory_csv_upload":
            kwargs["key"] = "ara_memory_mobile_safe_upload_v9"
        kwargs["help"] = "Accepts any file type. Choose your CSV file, or use the paste box."
    return _REAL_FILE_UPLOADER(_clean_ui_text(label), *args, **kwargs)


def branded_dg_selectbox(self, label, *args, **kwargs):
    return _REAL_DG_SELECTBOX(self, _clean_ui_text(label), *args, **kwargs)


def defaulted_st_number_input(label, *args, **kwargs):
    return _REAL_ST_NUMBER_INPUT(_clean_ui_text(label), *args, **_apply_number_default(label, kwargs))


def defaulted_st_slider(label, *args, **kwargs):
    if _slider_should_use_number_input(label):
        return _REAL_ST_NUMBER_INPUT(_clean_ui_text(label), *args, **_apply_slider_default(label, kwargs))
    return _REAL_ST_SLIDER(_clean_ui_text(label), *args, **_apply_slider_default(label, kwargs))


def defaulted_st_text_input(label, *args, **kwargs):
    return _REAL_ST_TEXT_INPUT(_clean_ui_text(label), *args, **_apply_text_default(label, kwargs))


def defaulted_st_toggle(label, *args, **kwargs):
    return _REAL_ST_TOGGLE(_clean_ui_text(label), *args, **_apply_toggle_default(label, kwargs))


def defaulted_dg_number_input(self, label, *args, **kwargs):
    return _REAL_DG_NUMBER_INPUT(self, _clean_ui_text(label), *args, **_apply_number_default(label, kwargs))


def defaulted_dg_slider(self, label, *args, **kwargs):
    if _slider_should_use_number_input(label):
        return _REAL_DG_NUMBER_INPUT(self, _clean_ui_text(label), *args, **_apply_slider_default(label, kwargs))
    return _REAL_DG_SLIDER(self, _clean_ui_text(label), *args, **_apply_slider_default(label, kwargs))


def defaulted_dg_text_input(self, label, *args, **kwargs):
    return _REAL_DG_TEXT_INPUT(self, _clean_ui_text(label), *args, **_apply_text_default(label, kwargs))


def defaulted_dg_toggle(self, label, *args, **kwargs):
    return _REAL_DG_TOGGLE(self, _clean_ui_text(label), *args, **_apply_toggle_default(label, kwargs))


def install_report_branding() -> None:
    try:
        from autonomous_betting_agent import odds_lock_tools
    except Exception:
        return
    original_daily_report = getattr(odds_lock_tools, "daily_report", None)
    if not callable(original_daily_report) or getattr(original_daily_report, "_aba_brand_patched", False):
        return

    def branded_daily_report(*args, **kwargs):
        report = original_daily_report(*args, **kwargs)
        text = str(report or "")
        if text.startswith(APP_NAME):
            return text
        return f"{BRANDED_REPORT_PREFIX}\n\n{text}"

    branded_daily_report._aba_brand_patched = True
    odds_lock_tools.daily_report = branded_daily_report


install_memory_read_merge(REPO_MEMORY_PATH)
install_report_branding()
st.set_page_config = safe_set_page_config
st.caption = scrubbed_caption
st.info = scrubbed_info
st.markdown = scrubbed_markdown
st.write = scrubbed_write
st.file_uploader = mobile_safe_file_uploader
st.number_input = defaulted_st_number_input
st.slider = defaulted_st_slider
st.text_input = defaulted_st_text_input
st.toggle = defaulted_st_toggle
DeltaGenerator.caption = scrubbed_dg_caption
DeltaGenerator.info = scrubbed_dg_info
DeltaGenerator.markdown = scrubbed_dg_markdown
DeltaGenerator.write = scrubbed_dg_write
DeltaGenerator.number_input = defaulted_dg_number_input
DeltaGenerator.selectbox = branded_dg_selectbox
DeltaGenerator.slider = defaulted_dg_slider
DeltaGenerator.text_input = defaulted_dg_text_input
DeltaGenerator.toggle = defaulted_dg_toggle

try:
    render_sidebar_brand()
    current_page = st.navigation(CORE_PAGES, position="hidden")
    current_page.run()
except AttributeError:
    import pages.pro_predictor  # noqa: F401,E402

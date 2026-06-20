from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_main_shell_uses_shared_sidebar_and_current_entrypoint() -> None:
    app = (repo_root() / 'app_streamlit.py').read_text(encoding='utf-8')
    shell = (repo_root() / 'streamlit_app.py').read_text(encoding='utf-8')
    assert "render_app_sidebar('home'" in app
    assert "from app_streamlit import *" in shell
    assert 'Streamlit Cloud entrypoint' in shell
    assert 'pages/ultra80_profit_mode.py' not in app
    assert 'pages/ultra80_profit_mode.py' not in shell


def test_streamlit_config_hides_native_sidebar() -> None:
    config = (repo_root() / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
    assert 'showSidebarNavigation = false' in config
    assert 'toolbarMode = "minimal"' in config


def test_shell_brand_and_workflow_text_are_current() -> None:
    app = (repo_root() / 'app_streamlit.py').read_text(encoding='utf-8')
    assert "page_title='ABA Signal Pro'" in app
    assert 'Powered by Reparodynamics' in app
    assert 'Pro Predictor' in app
    assert 'Odds Lock Pro' in app
    assert 'Public Proof Dashboard' in app
    assert 'Learning Memory' in app


def test_sitecustomize_keeps_streamlit_widgets_native() -> None:
    text = (repo_root() / 'sitecustomize.py').read_text(encoding='utf-8')
    assert 'builtins.get_secret = get_secret' in text
    assert 'intentionally does not monkey-patch Streamlit widgets' in text
    assert 'st.file_uploader =' not in text
    assert 'st.sidebar.radio =' not in text
    assert 'st.sidebar.selectbox =' not in text


def test_pro_predictor_default_patch_values() -> None:
    from autonomous_betting_agent.pro_predictor_defaults_patch import MULTI_DEFAULTS, NUMBER_DEFAULTS, PROFILE_VALUES

    assert NUMBER_DEFAULTS['Max sports'] == 50
    assert NUMBER_DEFAULTS['Max events per sport'] == 500
    assert MULTI_DEFAULTS['Bookmaker regions'] == ['us', 'us2', 'eu', 'uk']
    assert PROFILE_VALUES['baseline_accuracy_max_high_conf'] == 300
    assert PROFILE_VALUES['baseline_accuracy_min_high_prob'] == 0.58
    assert PROFILE_VALUES['baseline_accuracy_min_high_agent'] == 35.0


def test_signal_board_file_exists_and_exposes_workflow_actions() -> None:
    text = (repo_root() / 'pages' / 'signal_board.py').read_text(encoding='utf-8')
    assert 'A_top_candidate' in text
    assert 'B_high_confidence_test' in text
    assert 'C_research_volume' in text
    assert 'what_are_the_odds_latest_rows' in text
    assert 'pro_predictor_high_confidence_rows' in text

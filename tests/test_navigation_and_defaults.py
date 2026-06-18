from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_main_navigation_uses_signal_board_and_hides_ultra70() -> None:
    app = (repo_root() / 'app_streamlit.py').read_text(encoding='utf-8')
    shell = (repo_root() / 'streamlit_app.py').read_text(encoding='utf-8')
    assert 'pages/signal_board.py' in app
    assert 'pages/signal_board.py' in shell
    assert 'pages/ultra80_profit_mode.py' not in app
    assert 'pages/ultra80_profit_mode.py' not in shell


def test_streamlit_config_uses_custom_sidebar_links() -> None:
    config = (repo_root() / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
    assert 'showSidebarNavigation = false' in config
    assert 'custom-bottom-sidebar-links' in config


def test_shell_uses_custom_page_routing() -> None:
    shell = (repo_root() / 'streamlit_app.py').read_text(encoding='utf-8')
    assert "position='hidden'" in shell
    assert 'hidden-nav-custom-bottom-links' in shell


def test_sitecustomize_renders_sidebar_links_after_language() -> None:
    sitecustomize = (repo_root() / 'sitecustomize.py').read_text(encoding='utf-8')
    assert 'def _install_sidebar_page_links()' in sitecustomize
    assert 'st.sidebar.radio = radio' in sitecustomize
    assert 'st.sidebar.selectbox = selectbox' in sitecustomize
    assert "('Pro Predictor', 'pages/pro_predictor.py')" in sitecustomize


def test_signal_board_has_direct_sidebar_links() -> None:
    text = (repo_root() / 'pages' / 'signal_board.py').read_text(encoding='utf-8')
    assert 'def sidebar_nav()' in text
    assert "st.page_link(path, label=label)" in text
    assert "st.switch_page('pages/pro_predictor.py')" in text


def test_sitecustomize_skips_streamlit_hooks_in_ci() -> None:
    text = (repo_root() / 'sitecustomize.py').read_text(encoding='utf-8')
    assert "def _running_in_ci()" in text
    assert "os.getenv('CI'" in text
    assert "os.getenv('GITHUB_ACTIONS'" in text
    assert 'if _running_in_ci()' in text


def test_pro_predictor_default_patch_values() -> None:
    from autonomous_betting_agent.pro_predictor_defaults_patch import MULTI_DEFAULTS, NUMBER_DEFAULTS, PROFILE_VALUES

    assert NUMBER_DEFAULTS['Max sports'] == 50
    assert NUMBER_DEFAULTS['Max events per sport'] == 500
    assert MULTI_DEFAULTS['Bookmaker regions'] == ['us', 'us2', 'eu', 'uk']
    assert PROFILE_VALUES['baseline_accuracy_max_high_conf'] == 250
    assert PROFILE_VALUES['baseline_accuracy_min_high_prob'] == 0.60
    assert PROFILE_VALUES['baseline_accuracy_min_high_agent'] == 40.0


def test_signal_board_file_exists_and_exposes_workflow_actions() -> None:
    text = (repo_root() / 'pages' / 'signal_board.py').read_text(encoding='utf-8')
    assert 'A_top_candidate' in text
    assert 'B_high_confidence_test' in text
    assert 'C_research_volume' in text
    assert 'what_are_the_odds_latest_rows' in text
    assert 'pro_predictor_high_confidence_rows' in text

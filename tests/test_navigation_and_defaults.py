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


def test_streamlit_config_uses_branded_custom_tools() -> None:
    config = (repo_root() / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
    assert 'showSidebarNavigation = false' in config
    assert 'custom-brand-language-tools' in config


def test_shell_sidebar_order_is_brand_language_tools_pages() -> None:
    app = (repo_root() / 'app_streamlit.py').read_text(encoding='utf-8')
    assert "APP_BUILD = 'clean-shell-sidebar-v8'" in app
    assert "st.markdown('### :green[ABA] Signal :red[Pro]')" in app
    assert "st.caption(APP_TAGLINE)" in app
    assert "st.radio('Language'" in app
    assert "st.markdown('### ' + ('Herramientas' if _language == 'Español' else 'Tools'))" in app
    assert "st.page_link(_path, label=_nav_label(_label, _language))" in app
    assert "st.navigation(PAGES, position='hidden')" in app


def test_child_page_language_controls_are_suppressed_by_shell() -> None:
    app = (repo_root() / 'app_streamlit.py').read_text(encoding='utf-8')
    assert 'def _hidden_language_radio' in app
    assert 'def _hidden_language_selectbox' in app
    assert 'st.sidebar.radio = _hidden_language_radio' in app
    assert 'st.sidebar.selectbox = _hidden_language_selectbox' in app


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

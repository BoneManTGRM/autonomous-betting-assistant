from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_entrypoints_use_centralized_sidebar() -> None:
    app = (repo_root() / 'app_streamlit.py').read_text(encoding='utf-8')
    shell = (repo_root() / 'streamlit_app.py').read_text(encoding='utf-8')
    assert 'render_app_sidebar' in app
    assert 'render_app_sidebar' in shell
    assert 'pages/ultra80_profit_mode.py' not in app
    assert 'pages/ultra80_profit_mode.py' not in shell


def test_streamlit_config_uses_custom_sidebar_only() -> None:
    config = (repo_root() / '.streamlit' / 'config.toml').read_text(encoding='utf-8')
    assert 'showSidebarNavigation = false' in config
    assert 'centralized-page-sidebar' in config


def test_sidebar_nav_has_brand_language_and_tools() -> None:
    text = (repo_root() / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert "APP_TAGLINE = 'Powered by Reparodynamics'" in text
    assert 'def render_app_sidebar' in text
    assert '### :green[ABA] Signal :red[Pro]' in text
    assert "('Signal Board', 'Signal Board', 'pages/signal_board.py')" in text
    assert "('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor.py')" in text
    assert "('What Are the Odds', 'What Are the Odds', 'pages/what_are_the_odds.py')" in text


def test_main_pages_call_shared_sidebar() -> None:
    page_names = [
        'signal_board.py',
        'pro_predictor.py',
        'simulation_lab.py',
        'threshold_optimizer.py',
        'what_are_the_odds.py',
        'odds_lock_pro.py',
    ]
    for name in page_names:
        text = (repo_root() / 'pages' / name).read_text(encoding='utf-8')
        assert 'render_app_sidebar' in text, name


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

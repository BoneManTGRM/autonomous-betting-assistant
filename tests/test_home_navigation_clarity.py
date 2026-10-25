"""Home/navigation copy, contrast, and local-only behavior regressions."""
from __future__ import annotations

import builtins
import re
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from autonomous_betting_agent import sidebar_nav

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_provider_requests(monkeypatch):
    def fail_request(*args, **kwargs):
        raise AssertionError('Home/navigation must not request provider data')
    monkeypatch.setattr(requests.sessions.Session, 'request', fail_request)


@pytest.mark.parametrize('language', ['en', 'es'])
@pytest.mark.parametrize('configured', [False, True])
def test_home_has_one_start_action_and_explains_local_provider_status(language, configured, monkeypatch):
    monkeypatch.setattr(builtins, 'get_secret', lambda *names: 'SYNTHETIC_ONLY' if configured else '', raising=False)
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=60)
    if language == 'es':
        app.radio(key='aba_radio_global_language').set_value('Español').run(timeout=60)
    assert not app.exception
    links = list(app.main.get('page_link'))
    assert len(links) == 1
    assert links[0].proto.label == ('Open Pro Predictor' if language == 'en' else 'Abrir Predictor Pro')
    assert 'pro_predictor_volume' in links[0].proto.page
    main_text = '\n'.join(str(element.value) for kind in ('info', 'success', 'caption') for element in app.main.get(kind))
    for phrase in (('Core', 'Proof Center', 'Dashboard', 'Report Studio', 'Show advanced tools', 'Learning Memory', 'No API key') if language == 'en' else ('Principal', 'Centro de Prueba', 'Dashboard', 'Report Studio', 'Mostrar herramientas avanzadas', 'Memoria de Aprendizaje', 'No necesitas una clave API')):
        assert phrase in main_text
    assert 'Tools menu' not in main_text
    assert 'Proof Control Center' not in main_text
    status = '\n'.join(str(element.value) for element in app.sidebar.caption)
    assert 'BallDontLie (BDL)' in status
    if language == 'en':
        assert ('key configured' if configured else 'key not configured') in status
        assert ('have not been checked' if configured else 'saved data') in status
    else:
        assert ('clave configurada' if configured else 'clave no configurada') in status
        assert ('no se han comprobado' if configured else 'datos guardados') in status
    assert 'BDL: Missing' not in status and 'BDL: Enabled' not in status
    assert not any('reset_storage' in element.proto.page for element in app.get('page_link'))
    app.checkbox(key=sidebar_nav.ADVANCED_NAV_KEY).check().run(timeout=60)
    assert not app.exception
    assert any('reset_storage' in element.proto.page for element in app.sidebar.get('page_link'))
    assert len(app.main.get('page_link')) == 1


@pytest.mark.parametrize('language', ['en', 'es'])
@pytest.mark.parametrize('item', sidebar_nav.CORE_TOOLS, ids=lambda item: item[2])
def test_core_pages_share_screen_theme_with_empty_local_state(item, language, monkeypatch, tmp_path):
    from autonomous_betting_agent import commercial_platform_tools, pick_hold_store, report_feed_service
    from autonomous_betting_agent.ui_theme import APP_THEME_CSS
    # This is a navigation/empty-state check, not a test of a developer's ledger
    # or of records left by another test. Relocate storage, not business logic.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pick_hold_store, 'DATA_DIR', tmp_path / 'held')
    monkeypatch.setattr(report_feed_service, 'FEED_ROOT', tmp_path / 'report_feeds')
    original_ledger_path = commercial_platform_tools.persistent_ledger_path
    monkeypatch.setattr(commercial_platform_tools, 'persistent_ledger_path',
                        lambda workspace_id='', path=None: original_ledger_path(workspace_id, path=tmp_path / 'ledger.csv'))
    monkeypatch.setattr(builtins, 'get_secret', lambda *names: '', raising=False)
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py'))
    app.session_state['aba_test_window_id'] = 'synthetic_theme_navigation'
    app.run(timeout=60)
    if language == 'es':
        app.radio(key='aba_radio_global_language').set_value('Español').run(timeout=60)
    app.switch_page(item[2]).run(timeout=60)
    assert not app.exception
    assert any(element.value == APP_THEME_CSS for element in app.markdown)
    assert app.session_state[sidebar_nav.GLOBAL_LANGUAGE_KEY] == ('Español' if language == 'es' else 'English')
    app.switch_page('streamlit_app.py').run(timeout=60)
    assert not app.exception
    assert [element.value for element in app.title] == ['ABA Signal Pro']
    assert len(app.main.get('page_link')) == 1


def _rgb(hex_color):
    return tuple(int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5))


def _contrast(foreground, background):
    def luminance(rgb):
        values = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in rgb]
        return sum(weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), values))
    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_custom_sidebar_text_meets_normal_text_contrast_on_explicit_background():
    css = sidebar_nav.SIDEBAR_CSS
    brand = re.search(r'\.aba-sidebar-brand\s*\{([^}]+)\}', css).group(1)
    background = _rgb(re.search(r'background:\s*(#[0-9a-fA-F]{6})', brand).group(1))
    for selector in ('title', 'tagline', 'section'):
        declarations = re.search(r'\.aba-sidebar-' + selector + r'\s*\{([^}]+)\}', css).group(1)
        foreground = _rgb(re.search(r'color:\s*(#[0-9a-fA-F]{6})', declarations).group(1))
        if selector == 'section':
            section_background = _rgb(re.search(r'background:\s*(#[0-9a-fA-F]{6})', declarations).group(1))
        else:
            section_background = background
        assert _contrast(foreground, section_background) >= 4.5
    gradient = re.search(r'linear-gradient\(([^;]+)\)', css).group(1)
    colors = [_rgb(value) for value in re.findall(r'#[0-9a-fA-F]{6}', gradient)]
    assert len(colors) == 2
    # Check interpolated colors as well as stops, not just brand endpoints.
    for start, end in zip(colors, colors[1:]):
        for step in range(101):
            color = tuple(left + (right - left) * step / 100 for left, right in zip(start, end))
            for foreground in ('#eef7f4', '#bad1c6'):
                assert _contrast(_rgb(foreground), color) >= 4.5


def test_native_theme_matches_website_and_custom_css_is_screen_scoped():
    import tomllib
    from autonomous_betting_agent.ui_theme import APP_THEME_CSS
    theme = tomllib.loads((ROOT / '.streamlit/config.toml').read_text())['theme']
    assert theme == {
        'base': 'dark', 'primaryColor': '#397653',
        'backgroundColor': '#07120f', 'secondaryBackgroundColor': '#102018',
        'textColor': '#eef7f4', 'font': 'sans serif',
    }
    for foreground in ('#eef7f4', '#bad1c6', '#91aaa0'):
        for background in ('#07120f', '#102018', '#142c23'):
            assert _contrast(_rgb(foreground), _rgb(background)) >= 4.5
    for background in ('#b9efc9', '#ddffe5'):
        assert _contrast(_rgb('#082017'), _rgb(background)) >= 4.5
    # Native primary controls always use white text, even on legacy pages
    # without the shared CSS. Their dark-green fallback must be safe by itself.
    assert _contrast(_rgb('#ffffff'), _rgb(theme['primaryColor'])) >= 4.5
    for background in ('#07120f', '#102018'):
        assert _contrast(_rgb(theme['primaryColor']), _rgb(background)) >= 3
    # A dark inner / mint outer focus ring remains visible in either user theme.
    for light_background in ('#ffffff', '#f0f2f6'):
        assert _contrast(_rgb('#082017'), _rgb(light_background)) >= 3
    for dark_background in ('#07120f', '#102018', '#142c23'):
        assert _contrast(_rgb('#b9efc9'), _rgb(dark_background)) >= 3
    assert '[data-testid="stMain"] .aba-summary-hero' in APP_THEME_CSS
    assert '[data-testid="stMain"] .aba-mini-card' in APP_THEME_CSS
    assert 'iframe' not in APP_THEME_CSS
    assert 'stAlert' not in APP_THEME_CSS
    assert 'button:disabled' not in APP_THEME_CSS
    assert ':focus-visible' in APP_THEME_CSS
    assert '[data-testid="stBaseButton-primary"]:not(:disabled)' in APP_THEME_CSS
    assert 'background: #b9efc9; color: #082017;' in APP_THEME_CSS
    assert 'box-shadow: 0 0 0 6px #b9efc9' in APP_THEME_CSS
    assert '@media (max-width: 760px)' in APP_THEME_CSS

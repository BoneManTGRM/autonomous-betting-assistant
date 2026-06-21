from __future__ import annotations

from pathlib import Path


def test_sidebar_uses_colored_brand_and_safe_page_radio_selector() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert 'aba-sidebar-title' in text
    assert 'linear-gradient' in text
    assert "st.radio('Language / Idioma'" in text
    assert 'key=widget_key' in text
    assert 'on_change=_sync_global_from_radio' in text
    assert "widget_key = f'aba_radio_{language_key}'" in text
    assert "st.selectbox('Language / Idioma'" not in text
    assert 'aba-lang-pill' not in text


def test_sidebar_language_uses_safe_global_memory_key_and_avoids_legacy_widget_key_writes() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert "GLOBAL_LANGUAGE_KEY = 'aba_global_language'" in text
    assert 'st.session_state[GLOBAL_LANGUAGE_KEY] = language' in text
    assert "st.session_state['global_language'] = language" not in text
    assert 'st.session_state[language_key] = language' not in text
    assert 'def _sync_global_from_radio' in text
    assert 'st.page_link(path, label=label)' in text

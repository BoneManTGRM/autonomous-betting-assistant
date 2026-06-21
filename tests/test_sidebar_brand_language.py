from __future__ import annotations

from pathlib import Path


def test_sidebar_uses_colored_brand_and_stable_radio_selector() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert 'aba-sidebar-title' in text
    assert 'linear-gradient' in text
    assert "st.radio('Language / Idioma'" in text
    assert "key='aba_language_radio'" in text
    assert 'on_change=_sync_language_from_radio' in text
    assert "st.selectbox('Language / Idioma'" not in text
    assert 'aba-lang-pill' not in text


def test_sidebar_language_syncs_radio_to_global_key() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert 'def _sync_language_from_radio' in text
    assert "st.session_state['global_language'] = language" in text
    assert "'aba_language_radio', 'global_language'" in text
    assert 'st.page_link(path, label=label)' in text

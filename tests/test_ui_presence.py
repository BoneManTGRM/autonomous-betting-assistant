from __future__ import annotations

from pathlib import Path


def test_streamlit_app_contains_bilingual_page_selector_and_api_fields() -> None:
    text = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "Language / Idioma" in text
    assert "Pro Predictor" in text
    assert "market_snapshot_title" in text
    assert "odds_weather_title" in text
    assert "odds_api_key" in text
    assert "sportsdataio_key" in text
    assert "weatherapi_key" in text
    assert "render_market_capture" in text
    assert "render_context_layer" in text


def test_standalone_pages_contain_fields() -> None:
    market = Path("market_capture_page.py").read_text(encoding="utf-8")
    context = Path("context_layer_page.py").read_text(encoding="utf-8")
    assert "Language / Idioma" in market
    assert "odds_api_key" in market
    assert "book_regions" in market
    assert "max_api_calls" in market
    assert "Language / Idioma" in context
    assert "weatherapi_key" in context
    assert "sportsdataio_key" in context
    assert "manual_weather" in context

from __future__ import annotations

from pathlib import Path


def test_live_pro_predictor_page_has_multi_api_ui() -> None:
    text = Path("pages/pro_predictor.py").read_text(encoding="utf-8")
    assert "Provider key" not in text
    assert "Odds API key" in text
    assert "SportsDataIO key" in text
    assert "WeatherAPI key" in text
    assert "Run multi-API Predictor Pro" in text
    assert "Loaded from secrets" in text
    assert "fuse_row" in text
    assert "stats_adjustment" in text
    assert "injury_adjustment" in text
    assert "weather_adjustment" in text
    assert "final_probability" in text

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


def test_live_pro_predictor_page_has_70_target_mode() -> None:
    text = Path("pages/pro_predictor.py").read_text(encoding="utf-8")
    assert "70% ±1 Target Mode" in text
    assert "target_70_mode" in text
    assert "target_probability" in text
    assert "target_tolerance" in text
    assert "target_min_reliability" in text
    assert "target_70_rejection_reason" in text
    assert "price_probability_mismatch" in text
    assert "Download 70% target CSV" in text


def test_live_pro_predictor_page_has_strict_70_quality_controls() -> None:
    text = Path("pages/pro_predictor.py").read_text(encoding="utf-8")
    assert "target_min_market_probability" in text
    assert "target_min_ev" in text
    assert "target_max_mismatch" in text
    assert "target_70_quality_score" in text
    assert "duplicate_event_pick" in text
    assert "dedupe_key" in text
    assert "price_probability_gap" in text
    assert "estimated_ev_value" in text
    assert "market probability below floor" in text
    assert "EV below target" in text
    assert "duplicate event/pick" in text

from __future__ import annotations

import unittest
from pathlib import Path


class LivePageUiPresenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = Path("pages/pro_predictor.py").read_text(encoding="utf-8")

    def test_live_pro_predictor_page_has_multi_api_ui(self) -> None:
        self.assertNotIn("Provider key", self.text)
        self.assertIn("Odds API key", self.text)
        self.assertIn("SportsDataIO key", self.text)
        self.assertIn("WeatherAPI key", self.text)
        self.assertIn("Run multi-API Predictor Pro", self.text)
        self.assertIn("Loaded from secrets", self.text)
        self.assertIn("fuse_row", self.text)
        self.assertIn("stats_adjustment", self.text)
        self.assertIn("injury_adjustment", self.text)
        self.assertIn("weather_adjustment", self.text)
        self.assertIn("final_probability", self.text)

    def test_live_pro_predictor_page_has_70_target_mode(self) -> None:
        self.assertIn("70% ±1 Target Mode", self.text)
        self.assertIn("target_70_mode", self.text)
        self.assertIn("target_probability", self.text)
        self.assertIn("target_tolerance", self.text)
        self.assertIn("target_min_reliability", self.text)
        self.assertIn("target_70_rejection_reason", self.text)
        self.assertIn("price_probability_mismatch", self.text)
        self.assertIn("Download 70% target CSV", self.text)

    def test_live_pro_predictor_page_has_strict_70_quality_controls(self) -> None:
        self.assertIn("target_min_market_probability", self.text)
        self.assertIn("target_min_ev", self.text)
        self.assertIn("target_max_mismatch", self.text)
        self.assertIn("target_70_quality_score", self.text)
        self.assertIn("duplicate_event_pick", self.text)
        self.assertIn("dedupe_key", self.text)
        self.assertIn("price_probability_gap", self.text)
        self.assertIn("estimated_ev_value", self.text)
        self.assertIn("TargetModePolicy", self.text)
        self.assertIn("evaluate_target_mode", self.text)

    def test_live_pro_predictor_page_uses_real_api_context_builder(self) -> None:
        self.assertIn("LiveAPIContextBuilder", self.text)
        self.assertIn("context_builder.context_for_event", self.text)
        self.assertIn("odds_api_source_used", self.text)
        self.assertIn("sportsdataio_source_used", self.text)
        self.assertIn("stats_source_used", self.text)
        self.assertIn("injury_source_used", self.text)
        self.assertIn("weather_source_used", self.text)
        self.assertIn("sportsdataio_status", self.text)
        self.assertIn("weatherapi_status", self.text)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.ara_filters import (
    apply_ara_decision_layer,
    dedupe_ara_records,
    market_probability,
    parse_percent,
    proxy_filter_decision,
    risk_flags_for,
    sport_group,
    weather_flags_for,
)


class AraFilterTests(unittest.TestCase):
    def test_parse_percent_accepts_percent_and_decimal(self) -> None:
        self.assertEqual(parse_percent("55%"), 0.55)
        self.assertEqual(parse_percent("0.55"), 0.55)
        self.assertIsNone(parse_percent("not a number"))

    def test_sport_group_handles_american_football(self) -> None:
        self.assertEqual(sport_group("american football nfl"), "American football")
        self.assertEqual(sport_group("soccer premier league"), "Soccer")

    def test_soccer_draw_filter_blocks_high_draw_probability(self) -> None:
        row = {
            "Sport": "soccer",
            "Classification": "Strong",
            "Market probability": "58%",
            "Draw probability": "27%",
            "Data quality": 90,
            "Risk penalty": 5,
            "Best price": 1.90,
            "Books": 10,
        }
        self.assertIn("soccer_draw_risk_block_ml_25_plus", risk_flags_for(row))
        decision, _ = proxy_filter_decision(row)
        self.assertEqual(decision, "PROXY_WATCH_NO_ML")

    def test_weather_flags_for_outdoor_conditions(self) -> None:
        row = {"Sport": "mlb", "wind_mph": 18, "precip_mm": 3}
        flags = weather_flags_for(row)
        self.assertIn("weather_wind_watch", flags)
        self.assertIn("weather_precip_watch", flags)

    def test_weather_severe_uses_tokens(self) -> None:
        self.assertIn("weather_condition_severe", weather_flags_for({"Sport": "nfl", "weather_condition": "Thunder storm"}))
        self.assertNotIn("weather_condition_severe", weather_flags_for({"Sport": "nfl", "weather_condition": "Nice and clear"}))

    def test_weather_api_error_blocks_live_action(self) -> None:
        df = pd.DataFrame([
            {
                "Event": "Away at Home",
                "Start": "2026-01-01",
                "Prediction": "Home",
                "Sport": "mlb",
                "Market probability": "60%",
                "ARA model probability": "67%",
                "Classification": "Strong",
                "Data quality": 95,
                "Risk penalty": 5,
                "Best price": 1.80,
                "Books": 10,
                "weather_tier": "Error",
                "weather_error": "401 Client Error: Unauthorized",
            }
        ])
        enriched = apply_ara_decision_layer(df)
        self.assertIn("weather_api_error", enriched.iloc[0]["ara_risk_flags"])
        self.assertEqual(enriched.iloc[0]["ara_live_decision"], "WATCH")
        self.assertIn("weather_api_error", enriched.iloc[0]["ara_decision_reason"])

    def test_empty_frame_is_safe(self) -> None:
        enriched = apply_ara_decision_layer(pd.DataFrame())
        self.assertIn("ara_live_decision", enriched.columns)
        self.assertEqual(len(enriched), 0)

    def test_apply_layer_adds_columns_and_dedupes(self) -> None:
        df = pd.DataFrame([
            {"Event": "A", "Start": "2026-01-01", "Prediction": "Home", "Sport": "mlb", "Market probability": "60%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.90, "Books": 10, "result": "won"},
            {"Event": "A", "Start": "2026-01-01", "Prediction": "Home", "Sport": "mlb", "Market probability": "60%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.90, "Books": 10, "result": "won"},
        ])
        enriched = apply_ara_decision_layer(df)
        self.assertIn("ara_live_decision", enriched.columns)
        self.assertEqual(market_probability(enriched.iloc[0].to_dict()), 0.60)
        self.assertEqual(len(dedupe_ara_records(enriched)), 1)


if __name__ == "__main__":
    unittest.main()

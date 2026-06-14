from __future__ import annotations

import unittest

from autonomous_betting_agent.market_accuracy_profiles import build_market_profiles, enrich_with_market_profiles, profile_key, summarize_profiles


class MarketAccuracyProfileTests(unittest.TestCase):
    def test_profile_key_includes_core_segments(self) -> None:
        row = {"sport": "nfl", "market": "h2h", "best_price": "1.8", "data_quality": "85"}
        key = profile_key(row)
        self.assertIn("nfl|h2h", key)
        self.assertIn("quality_high", key)

    def test_builds_profiles_from_history(self) -> None:
        history = []
        for _ in range(25):
            history.append({"sport": "nfl", "market": "h2h", "best_price": "1.8", "data_quality": "85", "result": "won", "closing_line_value": "0.03"})
        for _ in range(5):
            history.append({"sport": "nfl", "market": "h2h", "best_price": "1.8", "data_quality": "85", "result": "lost", "closing_line_value": "0.01"})
        profiles = build_market_profiles(history, min_samples=10)
        self.assertTrue(any(key.startswith("nfl|h2h") for key in profiles))
        self.assertTrue(any(profile.accuracy_score > 50 for profile in profiles.values()))

    def test_enriches_rows_with_profile(self) -> None:
        history = []
        for _ in range(25):
            history.append({"sport": "nfl", "market": "h2h", "best_price": "1.8", "data_quality": "85", "result": "won"})
        for _ in range(5):
            history.append({"sport": "nfl", "market": "h2h", "best_price": "1.8", "data_quality": "85", "result": "lost"})
        rows = [{"sport": "nfl", "market": "h2h", "best_price": "1.8", "data_quality": "85"}]
        enriched = enrich_with_market_profiles(rows, history, min_samples=10)
        self.assertNotEqual(enriched[0]["profile_key"], "")
        self.assertNotEqual(enriched[0]["profile_accuracy_score"], "")
        self.assertIn(enriched[0]["profile_trust_level"], {"LOW", "MEDIUM", "HIGH"})

    def test_falls_back_to_low_trust_without_profile(self) -> None:
        enriched = enrich_with_market_profiles([{"sport": "mlb", "market": "total"}], [], min_samples=10)
        self.assertEqual(enriched[0]["profile_trust_level"], "LOW")
        self.assertEqual(enriched[0]["profile_key"], "")

    def test_summarizes_profiles(self) -> None:
        history = []
        for _ in range(12):
            history.append({"sport": "nfl", "market": "h2h", "best_price": "1.8", "data_quality": "85", "result": "won"})
        rows = enrich_with_market_profiles([{"sport": "nfl", "market": "h2h", "best_price": "1.8", "data_quality": "85"}], history, min_samples=10)
        report = summarize_profiles(rows, history)
        self.assertEqual(report.enriched_rows, 1)
        self.assertGreaterEqual(report.profile_count, 1)


if __name__ == "__main__":
    unittest.main()

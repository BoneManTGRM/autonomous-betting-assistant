from __future__ import annotations

import unittest

from autonomous_betting_agent.line_movement_model import (
    build_line_movement_profiles,
    enrich_line_movement_rows,
    movement_direction,
    movement_strength,
    summarize_line_movement,
)


class LineMovementModelTests(unittest.TestCase):
    def test_movement_direction_and_strength(self) -> None:
        self.assertEqual(movement_direction(1.8, 1.6), "toward_pick")
        self.assertEqual(movement_direction(1.6, 1.8), "against_pick")
        self.assertEqual(movement_direction(1.7, 1.7), "flat")
        self.assertAlmostEqual(movement_strength(1.8, 1.6) or 0, 0.111111, places=5)

    def test_builds_historical_profiles(self) -> None:
        rows = []
        for _ in range(12):
            rows.append({"sport": "nfl", "market": "h2h", "entry_odds": "1.8", "closing_odds": "1.6", "result": "won"})
        for _ in range(4):
            rows.append({"sport": "nfl", "market": "h2h", "entry_odds": "1.8", "closing_odds": "1.6", "result": "lost"})
        profiles = build_line_movement_profiles(rows, min_samples=10)
        self.assertIn("nfl|h2h|toward_pick", profiles)
        self.assertGreater(profiles["nfl|h2h|toward_pick"].market_support_score, 50)

    def test_enriches_rows_with_profile_support(self) -> None:
        history = []
        for _ in range(12):
            history.append({"sport": "nfl", "market": "h2h", "entry_odds": "1.8", "closing_odds": "1.6", "result": "won"})
        for _ in range(4):
            history.append({"sport": "nfl", "market": "h2h", "entry_odds": "1.8", "closing_odds": "1.6", "result": "lost"})
        rows = [{"sport": "nfl", "market": "h2h", "opening_odds": "1.9", "entry_odds": "1.8", "closing_odds": "1.6"}]
        enriched = enrich_line_movement_rows(rows, history, min_profile_samples=10)
        self.assertEqual(enriched[0]["line_movement_direction"], "toward_pick")
        self.assertNotEqual(enriched[0]["market_support_score"], "")
        self.assertNotEqual(enriched[0]["opening_to_entry_movement"], "")

    def test_summarizes_line_movement(self) -> None:
        rows = enrich_line_movement_rows([
            {"entry_odds": "1.8", "closing_odds": "1.6"},
            {"entry_odds": "1.6", "closing_odds": "1.8"},
        ])
        report = summarize_line_movement(rows)
        self.assertEqual(report.raw_rows, 2)
        self.assertEqual(report.positive_clv_rows, 1)
        self.assertEqual(report.negative_clv_rows, 1)


if __name__ == "__main__":
    unittest.main()

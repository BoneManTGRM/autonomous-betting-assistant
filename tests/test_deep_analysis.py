from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.deep_analysis import apply_deep_analysis, merge_latest_movement


class DeepAnalysisTests(unittest.TestCase):
    def test_deep_analysis_scores_candidate(self) -> None:
        frame = pd.DataFrame([
            {
                "Event": "Away at Home",
                "Sport": "mlb",
                "Start": "2026-06-14T20:00:00Z",
                "Prediction": "Home",
                "Market probability": "60%",
                "ARA model probability": "68%",
                "Classification": "Strong",
                "Data quality": 95,
                "Risk penalty": 5,
                "Best price": 1.80,
                "Books": 10,
                "result": "pending",
                "movement_signal": "STEAM",
                "movement_strength": "moderate",
                "market_confidence_score": 82,
            }
        ])
        enriched = apply_deep_analysis(frame)
        self.assertIn("ara_deep_score", enriched.columns)
        self.assertGreaterEqual(float(enriched.iloc[0]["ara_deep_score"]), 70)
        self.assertIn(enriched.iloc[0]["ara_deep_recommendation"], {"DEEP_READY", "DEEP_READY_STRONG", "DEEP_WATCH"})

    def test_avoid_is_penalized(self) -> None:
        frame = pd.DataFrame([
            {
                "Event": "Away at Home",
                "Sport": "soccer",
                "Start": "2026-06-14T20:00:00Z",
                "Prediction": "Home",
                "Market probability": "58%",
                "Classification": "Avoid",
                "Data quality": 70,
                "Risk penalty": 20,
                "Best price": 1.20,
                "Books": 3,
                "Draw probability": "31%",
            }
        ])
        enriched = apply_deep_analysis(frame)
        self.assertEqual(enriched.iloc[0]["ara_deep_recommendation"], "DEEP_AVOID")

    def test_merge_latest_movement_by_event_id_and_prediction(self) -> None:
        predictions = pd.DataFrame([{"event_id": "abc", "Prediction": "Home"}])
        movement = pd.DataFrame([{"event_id": "abc", "outcome": "Home", "movement_signal": "STEAM"}])
        merged = merge_latest_movement(predictions, movement)
        self.assertEqual(merged.iloc[0]["movement_signal"], "STEAM")


if __name__ == "__main__":
    unittest.main()

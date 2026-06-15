from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.audit import audit_dashboard_metrics, clean_grading_status, confidence_tier, decimal_to_american, enrich_prediction_frame, implied_probability_from_decimal, profit_units


class AuditTests(unittest.TestCase):
    def test_odds_conversions(self) -> None:
        self.assertEqual(decimal_to_american(2.0), 100)
        self.assertEqual(decimal_to_american(1.5), -200)
        self.assertEqual(implied_probability_from_decimal(1.25), 0.8)

    def test_profit_units(self) -> None:
        self.assertEqual(profit_units("win", 1.91, 1), 0.91)
        self.assertEqual(profit_units("loss", 1.91, 1), -1.0)
        self.assertEqual(profit_units("void", 1.91, 1), 0.0)
        self.assertIsNone(profit_units("pending", 1.91, 1))

    def test_grading_rules(self) -> None:
        self.assertEqual(clean_grading_status({"win_loss": "win"}), "graded_clean")
        self.assertEqual(clean_grading_status({"win_loss": "win", "notes": "format mismatch"}), "review_needed")
        self.assertEqual(clean_grading_status({"status": "postponed"}), "void")

    def test_confidence_tier(self) -> None:
        row = {"best_price": 1.72, "confidence": "high", "reliability_score": 96, "books": 5, "estimated_ev_value": 0.05, "api_coverage_score": 1.0, "target_70_mode": True}
        self.assertEqual(confidence_tier(row), "A+ High Confidence")
        self.assertEqual(confidence_tier({**row, "duplicate_event_pick": True}), "No Bet")

    def test_enrich_frame_and_metrics(self) -> None:
        frame = pd.DataFrame([
            {"event": "A at B", "best_price": 1.91, "win_loss": "win", "confidence": "high", "reliability_score": 95, "books": 5, "estimated_ev_value": 0.03, "api_coverage_score": 1, "target_70_mode": True},
            {"event": "C at D", "best_price": 2.10, "win_loss": "loss", "confidence": "high", "reliability_score": 91, "books": 4, "estimated_ev_value": 0.02},
            {"event": "E at F", "best_price": 1.50, "status": "pending"},
        ])
        enriched = enrich_prediction_frame(frame, prediction_timestamp="2026-06-15T18:54:00Z")
        self.assertIn("profit_units", enriched.columns)
        metrics = audit_dashboard_metrics(enriched)
        self.assertEqual(metrics["official_graded"], 2)
        self.assertEqual(metrics["wins"], 1)
        self.assertEqual(metrics["losses"], 1)
        self.assertAlmostEqual(metrics["units"], -0.09)


if __name__ == "__main__":
    unittest.main()

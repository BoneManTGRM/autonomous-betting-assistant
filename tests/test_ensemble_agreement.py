from __future__ import annotations

import unittest

from autonomous_betting_agent.ensemble_agreement import EnsemblePolicy, apply_ensemble_scoring, score_ensemble_row, summarize_ensemble


class EnsembleAgreementTests(unittest.TestCase):
    def test_accepts_row_with_many_agreeing_signals(self) -> None:
        row = {
            "calibrated_probability": "0.68",
            "edge": "0.06",
            "data_quality": "90",
            "bookmaker_count": "8",
            "closing_line_value": "0.04",
            "market_support_score": "75",
        }
        scored = score_ensemble_row(row)
        self.assertEqual(scored["ensemble_status"], "ACCEPT")
        self.assertGreaterEqual(float(scored["ensemble_score"]), 70)
        self.assertIn("probability", scored["signal_agreements"])

    def test_rejects_row_with_missing_and_low_signals(self) -> None:
        row = {"model_probability": "0.51", "edge": "-0.01", "data_quality": "40", "bookmaker_count": "1"}
        scored = score_ensemble_row(row)
        self.assertEqual(scored["ensemble_status"], "REJECT")
        self.assertIn("low_probability", scored["signal_conflicts"])
        self.assertIn("low_data_quality", scored["signal_conflicts"])

    def test_negative_flags_downgrade_pick(self) -> None:
        row = {
            "calibrated_probability": "0.68",
            "edge": "0.06",
            "data_quality": "90",
            "bookmaker_count": "8",
            "market_disagreement_flag": "true",
            "injury_flag": "true",
        }
        scored = score_ensemble_row(row)
        self.assertNotEqual(scored["ensemble_status"], "ACCEPT")
        self.assertIn("injury_flag", scored["signal_conflicts"])

    def test_apply_and_summarize(self) -> None:
        rows = [
            {"model_probability": "0.7", "edge": "0.05", "data_quality": "85", "bookmaker_count": "7", "market_support_score": "80"},
            {"model_probability": "0.51", "edge": "0", "data_quality": "30", "bookmaker_count": "1"},
        ]
        scored = apply_ensemble_scoring(rows)
        report = summarize_ensemble(scored)
        self.assertEqual(report.raw_rows, 2)
        self.assertEqual(report.accept_rows + report.watch_rows + report.reject_rows, 2)
        self.assertIsNotNone(report.average_ensemble_score)

    def test_custom_policy(self) -> None:
        policy = EnsemblePolicy(accept_score=60, min_accept_agreements=3, max_accept_conflicts=2)
        scored = score_ensemble_row({"model_probability": "0.64", "edge": "0.04", "data_quality": "90", "bookmaker_count": "5"}, policy=policy)
        self.assertIn(scored["ensemble_status"], {"ACCEPT", "WATCH"})


if __name__ == "__main__":
    unittest.main()

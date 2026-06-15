from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.mobile_report import compact_report_frame, prepare_mobile_report, rejection_summary
from autonomous_betting_agent.odds_breakdown import build_odds_breakdown


class MobileReportTests(unittest.TestCase):
    def test_rejection_summary_counts_missing_fields(self) -> None:
        frame = pd.DataFrame([
            {"event": "A at B", "prediction": "B", "decision": "watch_only", "decision_reason": "Not strong enough for the shortlist.", "probability_source": "missing", "best_price": "", "decimal_price": "", "estimated_ev_decimal": "", "odds_quality_score": 60},
            {"event": "C at D", "prediction": "C", "decision": "candidate", "probability_source": "model", "best_price": 1.9, "estimated_ev_decimal": 0.02, "odds_quality_score": 80},
        ])
        summary = rejection_summary(frame)
        issues = dict(zip(summary["Issue"], summary["Count"]))
        self.assertEqual(issues["Missing odds / price"], 1)
        self.assertEqual(issues["Missing probability source"], 1)
        self.assertEqual(issues["Watch only / not actionable"], 1)
        self.assertEqual(issues["Quality score below 70"], 1)
        self.assertEqual(issues["EV unavailable"], 1)

    def test_compact_report_uses_human_labels(self) -> None:
        frame = pd.DataFrame([
            {"event": "A at B", "prediction": "B", "decision": "watch_only", "decision_reason": "Not strong enough for the shortlist.", "best_price": 1.91, "decimal_price": 1.91, "confidence_tier": "Watch Only"}
        ])
        compact = compact_report_frame(frame)
        self.assertIn("Event", compact.columns)
        self.assertIn("Pick Status", compact.columns)
        self.assertEqual(compact.loc[0, "Pick Status"], "Watch Only")
        self.assertIn("No Bet", compact.loc[0, "Why"])

    def test_prepare_mobile_report_separates_actionable(self) -> None:
        frame = pd.DataFrame([
            {"event": "A at B", "prediction": "B", "best_price": 1.72, "confidence": "high", "reliability_score": 96, "books": 5, "estimated_ev_value": 0.05, "api_coverage_score": 1.0, "target_70_mode": True},
            {"event": "C at D", "prediction": "C", "decision": "watch_only", "best_price": "", "probability_source": "missing"},
        ])
        prepared = prepare_mobile_report(frame)
        self.assertEqual(len(prepared["actionable"]), 1)
        self.assertGreaterEqual(prepared["missing_odds_count"], 1)
        self.assertIn("compact", prepared)
        self.assertIn("rejection", prepared)

    def test_odds_breakdown_missing_price_gets_mobile_warning_data(self) -> None:
        source = pd.DataFrame([
            {"event": "A at B", "prediction": "B", "model_probability": "58%", "confidence": "HIGH"},
            {"event": "C at D", "prediction": "C", "model_probability": "72%", "best_price": 1.80, "confidence": "HIGH", "books": 5, "api_coverage_score": 1.0},
        ])
        main, props, diag = build_odds_breakdown(source)
        prepared = prepare_mobile_report(main)
        self.assertEqual(prepared["missing_odds_count"], 1)
        self.assertGreaterEqual(len(prepared["actionable"]), 1)
        self.assertFalse(props.empty)
        self.assertFalse(diag.empty)


if __name__ == "__main__":
    unittest.main()

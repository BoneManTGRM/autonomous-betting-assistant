from __future__ import annotations

import unittest

from autonomous_betting_agent.sportsdataio_quality import evaluate_pipeline_quality, quality_gate_allows


class SportsDataIOQualityTests(unittest.TestCase):
    def test_quality_passes_clean_pipeline(self) -> None:
        gate = evaluate_pipeline_quality(
            steps_run=["fetch_games", "apply_game_results", "build_player_features", "enrich_and_score_player_props"],
            warnings=[],
            counts={
                "prediction_rows": 10,
                "prediction_match_matched": 10,
                "odds_rows": 20,
                "odds_matched_rows": 10,
                "player_feature_records": 10,
                "player_feature_ready": 10,
                "player_prop_rows": 10,
                "player_feature_match_matched": 10,
                "profit_goal_finished_rows": 10,
                "profit_goal_wins": 7,
                "profit_goal_losses": 3,
                "profit_goal_status_goal_met": 1,
            },
        )
        self.assertEqual(gate.status, "PASS")
        self.assertEqual(gate.score, 100.0)
        self.assertIn("PASS: profit goal currently met for the reviewed sample", gate.reasons)

    def test_quality_fails_ambiguous_prediction_matches(self) -> None:
        gate = evaluate_pipeline_quality(
            steps_run=["apply_game_results"],
            warnings=[],
            counts={"prediction_rows": 10, "prediction_match_matched": 8, "prediction_match_ambiguous": 2},
        )
        self.assertEqual(gate.status, "FAIL")
        self.assertLess(gate.score, 100)
        self.assertTrue(any("ambiguous SportsDataIO matches" in reason for reason in gate.reasons))

    def test_quality_watches_low_player_feature_match_rate(self) -> None:
        gate = evaluate_pipeline_quality(
            steps_run=["enrich_and_score_player_props"],
            warnings=[],
            counts={"player_prop_rows": 10, "player_feature_match_matched": 7, "player_feature_match_unmatched": 3},
        )
        self.assertEqual(gate.status, "WATCH")
        self.assertAlmostEqual(float(gate.metrics["player_prop_feature_match_rate"]), 0.7)
        self.assertTrue(any("player prop feature match rate" in reason for reason in gate.reasons))

    def test_quality_fails_low_odds_match_rate_and_missing_entry(self) -> None:
        gate = evaluate_pipeline_quality(
            steps_run=["apply_game_results", "apply_odds_clv"],
            warnings=[],
            counts={
                "prediction_rows": 10,
                "prediction_match_matched": 10,
                "odds_rows": 10,
                "odds_matched_rows": 5,
                "odds_unmatched_rows": 5,
                "odds_missing_entry_rows": 1,
            },
        )
        self.assertEqual(gate.status, "FAIL")
        self.assertAlmostEqual(float(gate.metrics["odds_match_rate"]), 0.5)
        self.assertTrue(any("odds match rate" in reason for reason in gate.reasons))
        self.assertTrue(any("missing entry odds" in reason for reason in gate.reasons))

    def test_quality_fails_bad_profit_goal_checks(self) -> None:
        gate = evaluate_pipeline_quality(
            steps_run=["review_profit_goal"],
            warnings=[],
            counts={
                "profit_goal_finished_rows": 200,
                "profit_goal_wins": 140,
                "profit_goal_losses": 60,
                "profit_goal_status_not_met_yet": 1,
                "profit_goal_check_positive_roi_false": 1,
            },
        )
        self.assertEqual(gate.status, "FAIL")
        self.assertTrue(any("positive_roi_false" in reason for reason in gate.reasons))

    def test_quality_warns_on_pipeline_warnings(self) -> None:
        gate = evaluate_pipeline_quality(steps_run=[], warnings=["missing data"], counts={})
        self.assertEqual(gate.status, "WATCH")
        self.assertTrue(any("warning" in reason for reason in gate.reasons))

    def test_quality_gate_threshold_helper(self) -> None:
        pass_gate = evaluate_pipeline_quality(steps_run=[], warnings=[], counts={})
        watch_gate = evaluate_pipeline_quality(steps_run=[], warnings=["minor"], counts={})
        fail_gate = evaluate_pipeline_quality(steps_run=["apply_game_results"], warnings=[], counts={"prediction_rows": 10, "prediction_match_matched": 5})
        self.assertTrue(quality_gate_allows(pass_gate, minimum_status="PASS"))
        self.assertTrue(quality_gate_allows(pass_gate, minimum_status="WATCH"))
        self.assertFalse(quality_gate_allows(watch_gate, minimum_status="PASS"))
        self.assertTrue(quality_gate_allows(watch_gate, minimum_status="WATCH"))
        self.assertFalse(quality_gate_allows(fail_gate, minimum_status="WATCH"))
        self.assertTrue(quality_gate_allows(fail_gate, minimum_status="FAIL"))
        self.assertFalse(quality_gate_allows(None, minimum_status="FAIL"))

    def test_quality_gate_threshold_helper_rejects_unknown_minimum(self) -> None:
        gate = evaluate_pipeline_quality(steps_run=[], warnings=[], counts={})
        with self.assertRaises(ValueError):
            quality_gate_allows(gate, minimum_status="MAYBE")


if __name__ == "__main__":
    unittest.main()

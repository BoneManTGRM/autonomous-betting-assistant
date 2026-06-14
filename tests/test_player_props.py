from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.player_props import (
    apply_player_prop_layer,
    implied_probability_from_price,
    no_vig_binary_probability,
    normalize_prop_type,
    rank_player_props,
    score_player_prop,
)


class PlayerPropTests(unittest.TestCase):
    def test_no_vig_binary_probability(self) -> None:
        probability = no_vig_binary_probability(2.10, 1.80)
        self.assertIsNotNone(probability)
        expected = (1 / 2.10) / ((1 / 2.10) + (1 / 1.80))
        self.assertAlmostEqual(probability or 0, expected, places=6)

    def test_implied_probability_accepts_decimal_and_american_odds(self) -> None:
        self.assertAlmostEqual(implied_probability_from_price(2.00) or 0, 0.50)
        self.assertAlmostEqual(implied_probability_from_price(+150) or 0, 0.40)
        self.assertAlmostEqual(implied_probability_from_price(-120) or 0, 120 / 220)

    def test_normalizes_common_prop_types(self) -> None:
        self.assertEqual(normalize_prop_type("Anytime TD"), "touchdown")
        self.assertEqual(normalize_prop_type("HR"), "home_run")
        self.assertEqual(normalize_prop_type("Anytime Goal"), "goal")
        self.assertEqual(normalize_prop_type("Rushing Yards"), "rush_yards")

    def test_scores_qualified_player_prop_with_market_and_model(self) -> None:
        row = {
            "player_name": "Example RB",
            "prop_type": "Anytime TD",
            "best_price": 2.20,
            "model_probability": "55%",
            "books": 8,
            "data_quality": 90,
            "sample_size": 20,
        }
        scored = score_player_prop(row)
        self.assertEqual(scored["prop_type_normalized"], "touchdown")
        self.assertEqual(scored["prop_market_source"], "single_price_implied")
        self.assertEqual(scored["prop_status"], "QUALIFIED_STRONG")
        self.assertGreater(float(scored["prop_implied_edge"]), 0.08)
        self.assertGreaterEqual(float(scored["prop_confidence_score"]), 65)

    def test_no_vig_source_is_marked_separately(self) -> None:
        row = {
            "player_name": "Example WR",
            "prop_type": "Reception",
            "over_price": 2.10,
            "under_price": 1.80,
            "model_probability": "52%",
            "books": 8,
            "data_quality": 90,
            "sample_size": 20,
        }
        scored = score_player_prop(row)
        self.assertEqual(scored["prop_market_source"], "binary_no_vig")
        self.assertNotEqual(scored["prop_no_vig_probability"], "")

    def test_tracks_only_when_player_model_data_missing(self) -> None:
        row = {
            "player_name": "Example Batter",
            "prop_type": "Home Run",
            "best_price": 5.50,
            "books": 8,
            "data_quality": 90,
            "sample_size": 20,
        }
        scored = score_player_prop(row)
        self.assertEqual(scored["prop_status"], "TRACK_ONLY_NEEDS_PLAYER_MODEL_DATA")
        self.assertIn("player_model_probability_or_player_rates", scored["prop_required_data"])

    def test_rejects_bad_player_status(self) -> None:
        row = {
            "player_name": "Example Striker",
            "prop_type": "Goal",
            "best_price": 2.40,
            "model_probability": "48%",
            "books": 8,
            "data_quality": 90,
            "sample_size": 20,
            "injury_status": "out",
        }
        scored = score_player_prop(row)
        self.assertEqual(scored["prop_status"], "REJECT")
        self.assertIn("bad_player_status", scored["prop_reasons"])

    def test_small_sample_keeps_normal_edge_on_watch(self) -> None:
        row = {
            "player_name": "Example Forward",
            "prop_type": "Goal",
            "best_price": 2.00,
            "model_probability": "56%",
            "books": 8,
            "data_quality": 90,
            "sample_size": 4,
        }
        scored = score_player_prop(row)
        self.assertEqual(scored["prop_status"], "WATCH")
        self.assertIn("small_sample_size", scored["prop_reasons"])

    def test_apply_and_rank_player_props(self) -> None:
        frame = pd.DataFrame([
            {"player_name": "A", "prop_type": "TD", "best_price": 2.20, "model_probability": "55%", "books": 8, "data_quality": 90, "sample_size": 20},
            {"player_name": "B", "prop_type": "Goal", "best_price": 1.80, "model_probability": "50%", "books": 8, "data_quality": 90, "sample_size": 20},
        ])
        checked = apply_player_prop_layer(frame)
        self.assertIn("prop_status", checked.columns)
        self.assertIn("prop_market_source", checked.columns)
        self.assertIn("prop_confidence_score", checked.columns)
        ranked = rank_player_props(frame)
        self.assertGreaterEqual(len(ranked), 1)
        self.assertEqual(ranked.iloc[0]["player_name"], "A")


if __name__ == "__main__":
    unittest.main()

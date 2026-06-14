from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.player_prop_features import (
    build_feature_index,
    enrich_prop_with_player_feature,
    enrich_props_with_player_features,
    read_csv_rows,
    write_csv_rows,
)


class PlayerPropFeatureTests(unittest.TestCase):
    def test_build_feature_index_matches_by_id_and_name(self) -> None:
        features = [{"sdio_feature_player_id": "7", "display_name": "Jane Doe", "team": "DAL"}]
        by_id, by_name = build_feature_index(features)
        self.assertIn("7", by_id)
        self.assertIn("jane doe", by_name)

    def test_enriches_line_prop_with_season_rate(self) -> None:
        features = [{"sdio_feature_player_id": "7", "display_name": "Jane Doe", "team": "DAL", "games": "10", "rushing_yards_per_game": "80", "rushing_attempts_per_game": "15", "feature_ready": "true"}]
        by_id, by_name = build_feature_index(features)
        row = {"sdio_player_id": "7", "player_name": "Jane Doe", "prop_type": "rushing yards", "line": "70", "selection": "over", "best_price": "1.8"}
        enriched = enrich_prop_with_player_feature(row, by_id, by_name)
        self.assertEqual(enriched["feature_match_status"], "matched")
        self.assertEqual(enriched["feature_expected_value"], "80.0")
        self.assertGreater(float(enriched["season_rate"]), 0.5)
        self.assertEqual(enriched["sample_size"], "10")
        self.assertEqual(enriched["data_quality"], "90.0")

    def test_enriches_binary_prop_with_poisson_rate(self) -> None:
        features = [{"display_name": "Slugger", "team": "NYY", "games": "20", "home_runs_per_game": "0.25", "feature_ready": "true"}]
        enriched = enrich_props_with_player_features(
            [{"player_name": "Slugger", "prop_type": "home run", "selection": "yes", "best_price": "4.0"}],
            features,
        )[0]
        self.assertEqual(enriched["feature_match_status"], "matched")
        self.assertAlmostEqual(float(enriched["season_rate"]), 1.0 - 2.718281828459045 ** -0.25, places=4)

    def test_under_side_inverts_probability(self) -> None:
        features = [{"display_name": "Passer", "team": "DAL", "games": "10", "passing_yards_per_game": "250", "feature_ready": "true"}]
        enriched = enrich_props_with_player_features(
            [{"player_name": "Passer", "prop_type": "passing yards", "line": "300", "selection": "under"}],
            features,
        )[0]
        self.assertEqual(enriched["feature_match_status"], "matched")
        self.assertGreater(float(enriched["season_rate"]), 0.5)
        self.assertIn("inverted_for_under", enriched["feature_reason"])

    def test_ambiguous_name_does_not_enrich(self) -> None:
        features = [
            {"display_name": "Same Name", "team": "A", "games": "10", "points_per_game": "10"},
            {"display_name": "Same Name", "team": "B", "games": "10", "points_per_game": "12"},
        ]
        enriched = enrich_props_with_player_features([{"player_name": "Same Name", "prop_type": "points", "line": "10"}], features)[0]
        self.assertEqual(enriched["feature_match_status"], "ambiguous")
        self.assertEqual(enriched["feature_reason"], "no_unique_player_feature_match")

    def test_csv_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rows.csv"
            write_csv_rows([{"player_name": "A", "season_rate": "0.55"}], path)
            rows = read_csv_rows(path)
            self.assertEqual(rows[0]["player_name"], "A")


if __name__ == "__main__":
    unittest.main()

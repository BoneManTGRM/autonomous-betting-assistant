from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.sportsdataio_player_features import (
    build_player_feature,
    build_player_features,
    feature_fieldnames,
    read_csv_rows,
    write_player_features,
)


class SportsDataIOPlayerFeatureTests(unittest.TestCase):
    def test_builds_nfl_player_feature_rates(self) -> None:
        feature = build_player_feature(
            {
                "PlayerID": 7,
                "FirstName": "Jane",
                "LastName": "Doe",
                "Team": "DAL",
                "Position": "RB",
                "Season": 2026,
                "Games": 10,
                "RushingYards": 800,
                "RushingTouchdowns": 8,
                "Receptions": 30,
                "ReceivingYards": 250,
            },
            sport="nfl",
        )
        self.assertEqual(feature["sdio_feature_player_id"], "7")
        self.assertEqual(feature["display_name"], "Jane Doe")
        self.assertEqual(feature["sport"], "nfl")
        self.assertEqual(feature["rushing_yards"], "800")
        self.assertEqual(feature["rushing_yards_per_game"], "80.0")
        self.assertEqual(feature["rushing_touchdowns_per_game"], "0.8")
        self.assertEqual(feature["feature_ready"], "true")
        self.assertEqual(feature["feature_quality_flags"], "")

    def test_builds_mlb_player_feature_rates(self) -> None:
        feature = build_player_feature(
            {"PlayerID": 9, "Name": "Slugger", "Team": "NYY", "Games": 20, "HomeRuns": 5, "Hits": 30, "RunsBattedIn": 18},
            sport="mlb",
        )
        self.assertEqual(feature["home_runs_per_game"], "0.25")
        self.assertEqual(feature["hits_per_game"], "1.5")
        self.assertEqual(feature["rbis_per_game"], "0.9")

    def test_missing_fields_create_quality_flags(self) -> None:
        feature = build_player_feature({"Name": "Unknown", "Games": 0}, sport="nfl")
        self.assertEqual(feature["feature_ready"], "false")
        self.assertIn("missing_team", feature["feature_quality_flags"])
        self.assertIn("zero_games", feature["feature_quality_flags"])
        self.assertIn("no_core_stats", feature["feature_quality_flags"])

    def test_build_player_features_batch(self) -> None:
        features = build_player_features([
            {"PlayerID": 1, "Name": "A", "Team": "DAL", "Games": 1, "Points": 10},
            {"PlayerID": 2, "Name": "B", "Team": "NYG", "Games": 2, "Points": 12},
        ])
        self.assertEqual(len(features), 2)
        self.assertEqual(features[1]["points_per_game"], "6.0")

    def test_feature_fieldnames_include_core_and_rate_columns(self) -> None:
        names = feature_fieldnames([{"extra": "x"}])
        self.assertIn("sdio_feature_player_id", names)
        self.assertIn("passing_yards_per_game", names)
        self.assertIn("feature_quality_flags", names)
        self.assertIn("extra", names)

    def test_write_and_read_player_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "features.csv"
            features = [build_player_feature({"PlayerID": 7, "Name": "Jane Doe", "Team": "DAL", "Games": 10, "Points": 100})]
            write_player_features(features, path)
            rows = read_csv_rows(path)
            self.assertEqual(rows[0]["display_name"], "Jane Doe")
            self.assertEqual(rows[0]["points_per_game"], "10.0")


if __name__ == "__main__":
    unittest.main()

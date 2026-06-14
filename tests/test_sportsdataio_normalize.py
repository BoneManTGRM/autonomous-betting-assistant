from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.sportsdataio_normalize import (
    infer_dataset_type,
    normalize_game_record,
    normalize_player_record,
    normalize_records,
    normalize_team_record,
    write_normalized_csv,
)


class SportsDataIONormalizeTests(unittest.TestCase):
    def test_infers_games_dataset(self) -> None:
        records = [{"GameID": 1, "HomeTeam": "DAL", "AwayTeam": "NYG", "Status": "Final"}]
        self.assertEqual(infer_dataset_type(records), "games")

    def test_normalizes_game_record_and_winner(self) -> None:
        record = normalize_game_record(
            {
                "GameID": 10,
                "GlobalGameID": 100,
                "Season": 2026,
                "Week": 1,
                "DateTime": "2026-09-10T20:20:00",
                "Status": "Final",
                "HomeTeam": "DAL",
                "AwayTeam": "NYG",
                "HomeScore": 24,
                "AwayScore": 17,
            },
            sport="nfl",
        )
        self.assertEqual(record["sdio_dataset_type"], "games")
        self.assertEqual(record["sdio_game_id"], "10")
        self.assertEqual(record["sport"], "nfl")
        self.assertEqual(record["winner"], "DAL")
        self.assertEqual(record["is_final"], "true")
        self.assertEqual(record["source_quality_flags"], "")

    def test_game_missing_keys_get_quality_flags(self) -> None:
        record = normalize_game_record({"GameID": 10, "HomeTeam": "DAL"})
        self.assertIn("missing_away_team", record["source_quality_flags"])
        self.assertIn("missing_start_time", record["source_quality_flags"])

    def test_normalizes_player_record(self) -> None:
        record = normalize_player_record(
            {"PlayerID": 7, "FirstName": "Jane", "LastName": "Doe", "Team": "DAL", "Position": "RB", "Status": "Active"},
            sport="nfl",
        )
        self.assertEqual(record["sdio_dataset_type"], "players")
        self.assertEqual(record["display_name"], "Jane Doe")
        self.assertEqual(record["team"], "DAL")
        self.assertEqual(record["position"], "RB")

    def test_normalizes_team_record(self) -> None:
        record = normalize_team_record({"TeamID": 1, "Key": "DAL", "City": "Dallas", "Name": "Cowboys", "Conference": "NFC"}, sport="nfl")
        self.assertEqual(record["sdio_dataset_type"], "teams")
        self.assertEqual(record["team_key"], "DAL")
        self.assertEqual(record["full_name"], "Dallas Cowboys")

    def test_normalize_records_auto_uses_dataset_type(self) -> None:
        records = [{"PlayerID": 7, "Name": "Jane Doe", "Team": "DAL", "Position": "RB"}]
        normalized = normalize_records(records, dataset_type="auto", sport="nfl")
        self.assertEqual(normalized[0]["sdio_dataset_type"], "players")

    def test_write_normalized_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "games.csv"
            rows = [{"GameID": 1, "HomeTeam": "DAL", "AwayTeam": "NYG", "DateTime": "2026-09-10", "Status": "Scheduled"}]
            normalized = write_normalized_csv(rows, path, dataset_type="games", sport="nfl")
            self.assertEqual(len(normalized), 1)
            text = path.read_text(encoding="utf-8")
            self.assertIn("sdio_game_id", text.splitlines()[0])
            self.assertIn("DAL", text)


if __name__ == "__main__":
    unittest.main()

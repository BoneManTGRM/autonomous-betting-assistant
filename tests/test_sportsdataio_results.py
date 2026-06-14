from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.sportsdataio_results import (
    enrich_prediction_with_result,
    enrich_predictions_with_results,
    match_game,
    read_csv_rows,
    write_csv_rows,
)


class SportsDataIOResultsTests(unittest.TestCase):
    def test_matches_by_game_id_and_grades_win(self) -> None:
        prediction = {"sdio_game_id": "10", "prediction": "DAL"}
        games = [{"sdio_game_id": "10", "home_team": "DAL", "away_team": "NYG", "home_score": "24", "away_score": "17", "winner": "DAL", "status": "Final", "is_final": "true"}]
        enriched = enrich_prediction_with_result(prediction, games)
        self.assertEqual(enriched["sdio_result_match_status"], "matched")
        self.assertEqual(enriched["result"], "won")
        self.assertEqual(enriched["actual_winner"], "DAL")

    def test_matches_by_event_text_and_grades_loss(self) -> None:
        prediction = {"event": "NYG at DAL", "prediction": "NYG"}
        games = [{"sdio_game_id": "10", "home_team": "DAL", "away_team": "NYG", "home_score": "24", "away_score": "17", "winner": "DAL", "status": "Final", "is_final": "true"}]
        enriched = enrich_prediction_with_result(prediction, games)
        self.assertEqual(enriched["sdio_result_note"], "matched_by_event_text")
        self.assertEqual(enriched["result"], "lost")

    def test_matched_not_final_does_not_grade(self) -> None:
        prediction = {"event": "NYG at DAL", "prediction": "DAL"}
        games = [{"sdio_game_id": "10", "home_team": "DAL", "away_team": "NYG", "status": "Scheduled", "is_final": "false"}]
        enriched = enrich_prediction_with_result(prediction, games)
        self.assertEqual(enriched["sdio_result_match_status"], "not_final")
        self.assertEqual(enriched["result"], "")

    def test_ambiguous_match_is_not_graded(self) -> None:
        prediction = {"event": "NYG at DAL", "prediction": "DAL"}
        games = [
            {"sdio_game_id": "10", "home_team": "DAL", "away_team": "NYG", "status": "Final", "is_final": "true"},
            {"sdio_game_id": "11", "home_team": "DAL", "away_team": "NYG", "status": "Final", "is_final": "true"},
        ]
        status, game, note = match_game(prediction, games)
        self.assertEqual(status, "ambiguous")
        self.assertIsNone(game)
        self.assertEqual(note, "multiple_event_text_matches")

    def test_enrich_predictions_with_results(self) -> None:
        predictions = [{"event": "NYG at DAL", "prediction": "DAL"}]
        games = [{"sdio_game_id": "10", "home_team": "DAL", "away_team": "NYG", "home_score": "24", "away_score": "17", "winner": "DAL", "status": "Final", "is_final": "true"}]
        enriched = enrich_predictions_with_results(predictions, games)
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["result"], "won")

    def test_csv_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rows.csv"
            write_csv_rows([{"event": "NYG at DAL", "prediction": "DAL"}], path)
            rows = read_csv_rows(path)
            self.assertEqual(rows[0]["prediction"], "DAL")


if __name__ == "__main__":
    unittest.main()

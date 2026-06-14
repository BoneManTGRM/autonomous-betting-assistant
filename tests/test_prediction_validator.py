from __future__ import annotations

import unittest
from datetime import datetime, timezone

from autonomous_betting_agent.prediction_validator import ValidationPolicy, duplicate_key, validate_prediction_rows


class PredictionValidatorTests(unittest.TestCase):
    def test_valid_row_passes(self) -> None:
        rows = [{
            "sdio_game_id": "10",
            "start_time": "2026-09-10T20:20:00Z",
            "pick_time": "2026-09-10T12:00:00Z",
            "market": "h2h",
            "selection": "DAL",
            "model_probability": "0.64",
            "best_price": "1.8",
            "bookmaker_count": "5",
            "data_quality": "85",
        }]
        validated, report = validate_prediction_rows(rows, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(report.status, "PASS")
        self.assertEqual(validated[0]["validation_status"], "VALID")

    def test_missing_required_fields_fail(self) -> None:
        validated, report = validate_prediction_rows([{"event": "A at B"}], now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(validated[0]["validation_status"], "INVALID")
        self.assertIn("MISSING_MARKET", validated[0]["validation_errors"])

    def test_duplicate_key_prefers_game_id_market_selection(self) -> None:
        key = duplicate_key({"sdio_game_id": "10.0", "market": "h2h", "selection": "DAL"})
        self.assertEqual(key, ("game_id", "10", "h2h", "dal"))

    def test_duplicate_rows_are_errors(self) -> None:
        row = {
            "sdio_game_id": "10",
            "start_time": "2026-09-10T20:20:00Z",
            "pick_time": "2026-09-10T12:00:00Z",
            "market": "h2h",
            "selection": "DAL",
            "model_probability": "0.64",
            "best_price": "1.8",
        }
        _, report = validate_prediction_rows([row, row], now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(report.duplicate_rows, 1)
        self.assertEqual(report.status, "FAIL")

    def test_watch_when_quality_or_books_low(self) -> None:
        rows = [{
            "sdio_game_id": "10",
            "start_time": "2026-09-10T20:20:00Z",
            "pick_time": "2026-09-10T12:00:00Z",
            "market": "h2h",
            "selection": "DAL",
            "model_probability": "0.64",
            "best_price": "1.8",
            "bookmaker_count": "1",
            "data_quality": "50",
        }]
        validated, report = validate_prediction_rows(rows, ValidationPolicy(min_bookmaker_count=3, min_data_quality=70), now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(report.status, "WATCH")
        self.assertIn("LOW_BOOKMAKER_COUNT", validated[0]["validation_warnings"])
        self.assertIn("LOW_DATA_QUALITY", validated[0]["validation_warnings"])


if __name__ == "__main__":
    unittest.main()

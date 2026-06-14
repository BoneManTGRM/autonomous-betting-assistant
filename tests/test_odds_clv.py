from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.odds_clv import (
    enrich_predictions_with_odds,
    parse_price,
    read_csv_rows,
    summarize_odds_enrichment,
    write_csv_rows,
)


class OddsClvTests(unittest.TestCase):
    def test_parse_price_decimal_and_american(self) -> None:
        self.assertAlmostEqual(parse_price("1.80") or 0, 1.8)
        self.assertAlmostEqual(parse_price("+150") or 0, 2.5)
        self.assertAlmostEqual(parse_price("-200") or 0, 1.5)
        self.assertIsNone(parse_price("0.5"))

    def test_enriches_entry_closing_and_clv_by_game_id(self) -> None:
        predictions = [{"game_id": "10", "market": "h2h", "prediction": "DAL", "pick_time": "2026-09-10T12:00:00Z"}]
        odds = [
            {"game_id": "10", "market": "h2h", "selection": "DAL", "price": "1.70", "bookmaker": "a", "timestamp": "2026-09-10T10:00:00Z"},
            {"game_id": "10", "market": "h2h", "selection": "DAL", "price": "1.80", "bookmaker": "b", "timestamp": "2026-09-10T11:00:00Z"},
            {"game_id": "10", "market": "h2h", "selection": "DAL", "price": "1.60", "bookmaker": "a", "timestamp": "2026-09-10T20:00:00Z", "is_closing": "true"},
        ]
        enriched = enrich_predictions_with_odds(predictions, odds)
        row = enriched[0]
        self.assertEqual(row["odds_match_status"], "matched")
        self.assertEqual(row["entry_odds"], "1.8")
        self.assertEqual(row["closing_odds"], "1.6")
        self.assertAlmostEqual(float(row["closing_line_value"]), 0.111111, places=5)
        self.assertEqual(row["bookmaker_count"], "2")
        self.assertEqual(row["best_price"], "1.8")

    def test_does_not_use_future_nonclosing_entry_odds(self) -> None:
        predictions = [{"event": "DAL vs NYG", "market": "h2h", "prediction": "DAL", "pick_time": "2026-09-10T12:00:00Z"}]
        odds = [
            {"event": "DAL vs NYG", "market": "h2h", "selection": "DAL", "price": "1.70", "bookmaker": "a", "timestamp": "2026-09-10T11:00:00Z"},
            {"event": "DAL vs NYG", "market": "h2h", "selection": "DAL", "price": "2.10", "bookmaker": "b", "timestamp": "2026-09-10T13:00:00Z"},
            {"event": "DAL vs NYG", "market": "h2h", "selection": "DAL", "price": "1.60", "bookmaker": "a", "timestamp": "2026-09-10T20:00:00Z", "is_closing": "true"},
        ]
        row = enrich_predictions_with_odds(predictions, odds)[0]
        self.assertEqual(row["entry_odds"], "1.7")

    def test_unmatched_row_gets_quality_flag(self) -> None:
        row = enrich_predictions_with_odds([{"event": "A vs B", "prediction": "A"}], [])[0]
        self.assertEqual(row["odds_match_status"], "unmatched")
        self.assertIn("missing_odds_match", row["odds_quality_flags"])

    def test_summarizes_enrichment(self) -> None:
        rows = [
            {"odds_match_status": "matched", "entry_odds": "1.8", "closing_line_value": "0.1"},
            {"odds_match_status": "unmatched", "odds_quality_flags": "missing_odds_match"},
        ]
        report = summarize_odds_enrichment(rows)
        self.assertEqual(report.raw_rows, 2)
        self.assertEqual(report.matched_rows, 1)
        self.assertEqual(report.unmatched_rows, 1)
        self.assertAlmostEqual(report.average_entry_odds or 0, 1.8)

    def test_csv_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rows.csv"
            write_csv_rows([{"event": "A vs B", "prediction": "A"}], path)
            rows = read_csv_rows(path)
            self.assertEqual(rows[0]["prediction"], "A")


if __name__ == "__main__":
    unittest.main()

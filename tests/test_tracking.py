from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.tracking import (
    PredictionLedgerRow,
    RESULT_LOSS,
    RESULT_WIN,
    choose_decision,
    confidence_bucket,
    decimal_to_implied_probability,
    enrich_row,
    read_prediction_csv,
    summarize_tracking,
    write_ledger_csv,
)


class TrackingTests(unittest.TestCase):
    def test_implied_probability_and_decision(self) -> None:
        implied = decimal_to_implied_probability(2.0)
        self.assertEqual(implied, 0.5)
        decision = choose_decision(0.57, 2.0)
        self.assertEqual(decision.decision, "WATCH")
        self.assertGreater(decision.expected_value or 0.0, 0.0)

    def test_enrich_row_computes_edge_and_profit_loss(self) -> None:
        row = enrich_row(
            PredictionLedgerRow(
                event_name="Game A",
                sport="mlb",
                predicted_winner="Team A",
                model_probability=0.58,
                calibrated_probability=0.61,
                sportsbook_odds=1.95,
                result=RESULT_WIN,
            )
        )
        self.assertAlmostEqual(row.implied_probability or 0.0, 1 / 1.95)
        self.assertGreater(row.edge or 0.0, 0.0)
        self.assertAlmostEqual(row.profit_loss or 0.0, 0.95)
        self.assertEqual(row.confidence_bucket, "60-65%")

    def test_summary_tracks_groups_and_roi(self) -> None:
        rows = [
            PredictionLedgerRow("Game A", sport="mlb", calibrated_probability=0.61, sportsbook_odds=1.95, result=RESULT_WIN),
            PredictionLedgerRow("Game B", sport="mlb", calibrated_probability=0.57, sportsbook_odds=1.90, result=RESULT_LOSS),
            PredictionLedgerRow("Game C", sport="nba", calibrated_probability=0.63, sportsbook_odds=2.05, result=RESULT_WIN),
        ]
        report = summarize_tracking(rows)
        self.assertEqual(report.resolved_picks, 3)
        self.assertEqual(report.wins, 2)
        self.assertEqual(report.losses, 1)
        self.assertIsNotNone(report.brier_score)
        self.assertEqual(len(report.by_sport), 2)

    def test_read_and_write_tracking_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "predictions.csv"
            ledger = Path(tmp) / "ledger.csv"
            source.write_text(
                "event_name,sport,prediction,calibrated_probability,sportsbook_odds,result\n"
                "Game A,mlb,Team A,61%,1.95,won\n"
                "Game B,nba,Team B,0.57,1.90,lost\n",
                encoding="utf-8",
            )
            rows = read_prediction_csv(source)
            write_ledger_csv(rows, ledger)
            written = ledger.read_text(encoding="utf-8")
        self.assertEqual(len(rows), 2)
        self.assertIn("confidence_bucket", written)
        self.assertIn("profit_loss", written)

    def test_confidence_bucket(self) -> None:
        self.assertEqual(confidence_bucket(0.516), "50-55%")
        self.assertEqual(confidence_bucket(0.599), "55-60%")
        self.assertEqual(confidence_bucket(0.80), "80%+")


if __name__ == "__main__":
    unittest.main()

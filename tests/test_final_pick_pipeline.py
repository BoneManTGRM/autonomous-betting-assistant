from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.final_pick_pipeline import run_final_pick_pipeline


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class FinalPickPipelineTests(unittest.TestCase):
    def test_pipeline_writes_split_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            predictions = base / "predictions.csv"
            history = base / "history.csv"
            _write_csv(predictions, [
                {"sport": "nfl", "market": "h2h", "selection": "A", "model_probability": "0.72", "edge": "0.08", "best_price": "1.9", "data_quality": "90", "bookmaker_count": "8", "entry_odds": "1.9", "closing_odds": "1.7"},
                {"sport": "nfl", "market": "h2h", "selection": "B", "model_probability": "0.51", "edge": "0.00", "best_price": "1.6", "data_quality": "40", "bookmaker_count": "1"},
            ])
            history_rows = []
            for _ in range(15):
                history_rows.append({"sport": "nfl", "market": "h2h", "model_probability": "0.72", "result": "won", "best_price": "1.9", "entry_odds": "1.9", "closing_odds": "1.7", "data_quality": "90"})
            for _ in range(5):
                history_rows.append({"sport": "nfl", "market": "h2h", "model_probability": "0.72", "result": "lost", "best_price": "1.9", "entry_odds": "1.9", "closing_odds": "1.7", "data_quality": "90"})
            _write_csv(history, history_rows)

            report = run_final_pick_pipeline(
                predictions_csv=predictions,
                output_dir=base / "out",
                calibration_history_csv=history,
                line_movement_history_csv=history,
                market_profile_history_csv=history,
            )
            self.assertEqual(report.raw_rows, 2)
            self.assertEqual(report.final_bets + report.watchlist + report.rejected, 2)
            self.assertTrue(Path(report.outputs.all_scored_csv).exists())
            self.assertTrue(Path(report.outputs.final_bets_csv).exists())
            self.assertTrue(Path(report.outputs.daily_report_json).exists())


if __name__ == "__main__":
    unittest.main()

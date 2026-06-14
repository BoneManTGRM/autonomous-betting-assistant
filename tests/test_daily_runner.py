from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.daily_runner import run_daily_agent


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class DailyRunnerTests(unittest.TestCase):
    def test_manual_run_does_not_require_automation_toggle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            predictions = base / "predictions.csv"
            _write_csv(predictions, [{"sport": "nfl", "market": "h2h", "selection": "A", "model_probability": "0.72", "edge": "0.08", "best_price": "1.9", "data_quality": "90", "bookmaker_count": "8"}])
            report = run_daily_agent(predictions_csv=predictions, output_root=base / "daily", db_path=base / "picks.sqlite")
            self.assertEqual(report.run_mode, "manual")
            self.assertFalse(report.automated_daily_enabled)
            self.assertEqual(report.stored_rows, 1)
            self.assertTrue(Path(report.report_json).exists())

    def test_automated_daily_requires_explicit_toggle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            predictions = base / "predictions.csv"
            _write_csv(predictions, [{"sport": "nfl", "market": "h2h", "selection": "A", "model_probability": "0.72", "edge": "0.08", "best_price": "1.9"}])
            with self.assertRaises(ValueError):
                run_daily_agent(predictions_csv=predictions, output_root=base / "daily", db_path=base / "picks.sqlite", run_mode="automated_daily")
            report = run_daily_agent(predictions_csv=predictions, output_root=base / "daily", db_path=base / "picks.sqlite", run_mode="automated_daily", automated_daily_enabled=True)
            self.assertEqual(report.run_mode, "automated_daily")
            self.assertTrue(report.automated_daily_enabled)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.accuracy_calibration import (
    apply_calibration,
    calibrate_probability,
    fit_calibration_model,
    parse_probability,
    read_csv_rows,
    write_csv_rows,
)


class AccuracyCalibrationTests(unittest.TestCase):
    def test_parse_probability_accepts_percent_and_decimal(self) -> None:
        self.assertEqual(parse_probability("70"), 0.7)
        self.assertEqual(parse_probability("0.65"), 0.65)
        self.assertIsNone(parse_probability("120"))

    def test_fit_calibration_model_uses_observed_bucket_rate(self) -> None:
        history = []
        for _ in range(30):
            history.append({"model_probability": "0.70", "result": "won"})
        for _ in range(10):
            history.append({"model_probability": "0.70", "result": "lost"})
        model = fit_calibration_model(history, bucket_size=0.05, min_bucket_samples=10, shrinkage_strength=0)
        calibrated, reason, bucket = calibrate_probability(0.70, model)
        self.assertEqual(reason, "bucket_observed_shrunk")
        self.assertEqual(bucket, "0.70-0.75")
        self.assertAlmostEqual(calibrated or 0, 0.75)

    def test_apply_calibration_adds_columns(self) -> None:
        history = []
        for _ in range(20):
            history.append({"sport": "nfl", "market": "h2h", "model_probability": "0.65", "result": "won"})
        for _ in range(10):
            history.append({"sport": "nfl", "market": "h2h", "model_probability": "0.65", "result": "lost"})
        predictions = [{"sport": "nfl", "market": "h2h", "model_probability": "0.65"}]
        calibrated, report = apply_calibration(predictions, history, min_bucket_samples=5, shrinkage_strength=0, min_scope_samples=10)
        self.assertEqual(len(calibrated), 1)
        self.assertIn("calibrated_probability", calibrated[0])
        self.assertEqual(calibrated[0]["calibration_scope"], "nfl|h2h")
        self.assertEqual(report.calibrated_rows, 1)
        self.assertEqual(report.usable_rows, 30)

    def test_low_sample_bucket_uses_shrinkage(self) -> None:
        history = [{"model_probability": "0.80", "result": "won"}, {"model_probability": "0.80", "result": "lost"}]
        model = fit_calibration_model(history, min_bucket_samples=20, shrinkage_strength=25)
        calibrated, reason, _ = calibrate_probability(0.80, model)
        self.assertEqual(reason, "low_sample_bucket_shrunk")
        self.assertIsNotNone(calibrated)

    def test_csv_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rows.csv"
            write_csv_rows([{"model_probability": "0.7", "result": "won"}], path)
            rows = read_csv_rows(path)
            self.assertEqual(rows[0]["result"], "won")


if __name__ == "__main__":
    unittest.main()

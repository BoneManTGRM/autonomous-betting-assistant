from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.accuracy_calibration import (
    apply_calibration,
    brier_score,
    calibrate_probability,
    expected_calibration_error,
    fit_calibration_model,
    parse_probability,
    parse_result,
    result_from_row,
    read_csv_rows,
    write_csv_rows,
)


class AccuracyCalibrationTests(unittest.TestCase):
    def test_zero_and_false_grades_are_not_missing(self) -> None:
        for value in (0, 0.0, "0", "0.0", False, "false"):
            self.assertEqual(parse_result(value), "loss")
        self.assertEqual(parse_probability(0), 0.0)

    def test_final_grades_are_exact_and_conflicts_fail_closed(self) -> None:
        self.assertEqual(result_from_row({"result_status": "WIN", "status": "settled"}), "win")
        self.assertIsNone(result_from_row({"result_status": "win", "result": "loss"}))
        for alias in ("Result Status", "Result-Status"):
            self.assertIsNone(result_from_row({"result_status": "loss", alias: "win"}))
        self.assertIsNone(result_from_row({"result_status": "win", "status": "pending win verification"}))
        for value in ("would have won", "incorrect prediction", "win if home", "pending win verification"):
            self.assertIsNone(parse_result(value))
        model = fit_calibration_model([{"model_probability": 0.7, "result_status": "win"}])
        self.assertEqual(model.global_samples, 1)

    def test_calibration_is_idempotent_and_preserves_raw_input(self) -> None:
        history = [{"model_probability": 0.8, "result_status": "win"}] * 20 + [{"model_probability": 0.8, "result_status": "loss"}] * 10
        original = [{"model_probability": 0.8}]
        first, first_report = apply_calibration(original, history, min_bucket_samples=5, shrinkage_strength=0)
        second, second_report = apply_calibration(first, history, min_bucket_samples=5, shrinkage_strength=0)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["raw_model_probability"], "0.8")
        self.assertEqual(original, [{"model_probability": 0.8}])
        self.assertEqual(first_report, second_report)

    def test_repeated_calibration_preserves_boundary_precision(self) -> None:
        history = [{"model_probability": 0.6999996, "result": "win"}] * 20 + [{"model_probability": 0.70, "result": "loss"}] * 20
        first, _ = apply_calibration([{"model_probability": 0.6999996}], history, min_bucket_samples=1, shrinkage_strength=0)
        second, _ = apply_calibration(first, history, min_bucket_samples=1, shrinkage_strength=0)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["raw_model_probability"], "0.6999996")

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
        self.assertIsNone(report.raw_brier_score)
        self.assertIsNone(report.calibrated_brier_score)

    def test_apply_calibration_reports_accuracy_metrics_when_results_exist(self) -> None:
        history = []
        for _ in range(20):
            history.append({"model_probability": "0.80", "result": "won"})
        for _ in range(10):
            history.append({"model_probability": "0.80", "result": "lost"})
        predictions = [
            {"model_probability": "0.80", "result": "won"},
            {"model_probability": "0.80", "result": "lost"},
        ]
        calibrated, report = apply_calibration(predictions, history, min_bucket_samples=5, shrinkage_strength=0)
        self.assertEqual(len(calibrated), 2)
        self.assertIsNotNone(report.raw_brier_score)
        self.assertIsNotNone(report.calibrated_brier_score)
        self.assertIsNotNone(report.raw_expected_calibration_error)
        self.assertIsNotNone(report.calibrated_expected_calibration_error)

    def test_brier_and_expected_calibration_error(self) -> None:
        rows = [
            {"model_probability": "0.80", "result": "won"},
            {"model_probability": "0.20", "result": "lost"},
        ]
        self.assertAlmostEqual(brier_score(rows) or 0, 0.04)
        self.assertIsNotNone(expected_calibration_error(rows, bucket_size=0.1))

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

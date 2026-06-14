from __future__ import annotations

import unittest

from autonomous_betting_agent.calibration_review import parse_probability, parse_result, review_calibration_rows


class CalibrationReviewTests(unittest.TestCase):
    def test_parse_probability_accepts_percent_and_decimal(self) -> None:
        self.assertAlmostEqual(parse_probability("55%") or 0, 0.55)
        self.assertAlmostEqual(parse_probability("0.62") or 0, 0.62)
        self.assertIsNone(parse_probability("unknown"))

    def test_parse_result_accepts_common_labels(self) -> None:
        self.assertEqual(parse_result("won"), 1)
        self.assertEqual(parse_result("lost"), 0)
        self.assertIsNone(parse_result("pending"))

    def test_review_detects_overconfident_strong_bucket(self) -> None:
        rows = []
        for index in range(10):
            rows.append({
                "event": f"strong {index}",
                "classification": "Strong",
                "probability": "70%",
                "result": "won" if index < 5 else "lost",
                "sport": "soccer",
            })
        report = review_calibration_rows(rows, min_records=10, gap_threshold=0.08)
        strong = report["by_classification"]["Strong"]
        self.assertEqual(strong["records"], 10)
        self.assertEqual(strong["recommendation"], "DOWNWEIGHT")
        self.assertLess(strong["calibration_gap"], 0)

    def test_review_marks_small_samples(self) -> None:
        rows = [
            {"classification": "Watch", "probability": "55%", "result": "won"},
            {"classification": "Watch", "probability": "55%", "result": "lost"},
        ]
        report = review_calibration_rows(rows, min_records=10, gap_threshold=0.08)
        self.assertEqual(report["by_classification"]["Watch"]["recommendation"], "INSUFFICIENT_SAMPLE")
        self.assertEqual(report["settings"]["usable_finished_rows"], 2)


if __name__ == "__main__":
    unittest.main()

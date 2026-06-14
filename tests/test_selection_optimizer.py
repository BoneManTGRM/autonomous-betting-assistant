from __future__ import annotations

import unittest

from autonomous_betting_agent.selection_optimizer import SelectionRule, optimize_selection_rows


def _row(day: int, result: str, prob: float = 0.7, edge: float = 0.06, quality: float = 85, books: int = 8, odds: float = 1.8):
    return {
        "pick_time": f"2026-01-{day:02d}T10:00:00Z",
        "result": result,
        "model_probability": str(prob),
        "edge": str(edge),
        "data_quality": str(quality),
        "bookmaker_count": str(books),
        "best_price": str(odds),
    }


class SelectionOptimizerTests(unittest.TestCase):
    def test_optimizer_finds_rule_and_reports_test_metrics(self) -> None:
        rows = []
        for day in range(1, 31):
            rows.append(_row(day, "won" if day % 3 else "lost", prob=0.72, edge=0.06, quality=90, books=8, odds=1.75))
        for day in range(31, 41):
            rows.append(_row(day, "lost", prob=0.50, edge=0.00, quality=40, books=1, odds=1.5))
        report = optimize_selection_rows(rows, train_fraction=0.7, min_train_selected=5, min_test_selected=3)
        self.assertIn(report.status, {"PASS", "WATCH"})
        self.assertIsNotNone(report.best_rule)
        self.assertIsNotNone(report.train_metrics)
        self.assertIsNotNone(report.test_metrics)
        self.assertGreater(report.test_metrics.rows, 0)

    def test_optimizer_returns_no_rule_when_too_few_selected_rows(self) -> None:
        rows = [_row(1, "won"), _row(2, "lost")]
        report = optimize_selection_rows(rows, min_train_selected=10, min_test_selected=10)
        self.assertEqual(report.status, "NO_RULE_FOUND")
        self.assertIsNone(report.best_rule)

    def test_optimizer_warns_when_test_roi_negative(self) -> None:
        rows = []
        for day in range(1, 21):
            rows.append(_row(day, "won", prob=0.75, edge=0.08, quality=90, books=8, odds=1.8))
        for day in range(21, 31):
            rows.append(_row(day, "lost", prob=0.75, edge=0.08, quality=90, books=8, odds=1.8))
        report = optimize_selection_rows(rows, train_fraction=0.67, min_train_selected=5, min_test_selected=5)
        self.assertEqual(report.status, "WATCH")
        self.assertTrue(any("positive ROI" in action for action in report.required_actions))

    def test_selection_rule_is_serializable_dataclass(self) -> None:
        rule = SelectionRule(0.6, 0.05, 70.0, 5, 1.3, 3.0)
        self.assertEqual(rule.min_probability, 0.6)


if __name__ == "__main__":
    unittest.main()

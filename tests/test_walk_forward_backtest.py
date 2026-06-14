from __future__ import annotations

import unittest

from autonomous_betting_agent.walk_forward_backtest import run_walk_forward_backtest_rows


def _row(day: int, result: str = "win"):
    return {
        "pick_time": f"2026-01-{day:02d}T10:00:00Z",
        "sport": "nfl",
        "market": "h2h",
        "model_probability": "0.70",
        "edge": "0.06",
        "best_price": "1.8",
        "data_quality": "85",
        "bookmaker_count": "7",
        "result": result,
    }


class WalkForwardBacktestTests(unittest.TestCase):
    def test_walk_forward_creates_folds(self) -> None:
        rows = [_row(day, "win" if day % 3 else "loss") for day in range(1, 31)]
        report = run_walk_forward_backtest_rows(rows, train_size=10, test_size=5, min_selected_per_fold=1)
        self.assertGreater(report.folds, 0)
        self.assertGreater(report.total_test_rows, 0)
        self.assertGreaterEqual(report.total_selected_rows, 1)
        self.assertIn(report.status, {"PASS", "WATCH"})
        self.assertIsNotNone(report.aggregate_win_rate)

    def test_walk_forward_fails_without_enough_rows(self) -> None:
        report = run_walk_forward_backtest_rows([_row(1)], train_size=10, test_size=5)
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(report.folds, 0)

    def test_max_losing_streak_reported(self) -> None:
        rows = [_row(day, "loss" if day in {11, 12, 13} else "win") for day in range(1, 16)]
        report = run_walk_forward_backtest_rows(rows, train_size=10, test_size=5, min_selected_per_fold=1)
        self.assertGreaterEqual(report.max_losing_streak, 0)


if __name__ == "__main__":
    unittest.main()

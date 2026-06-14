from __future__ import annotations

import unittest

from autonomous_betting_agent.backtest_engine import BacktestPolicy, audit_row_for_leakage, run_backtest_rows


def _row(day: int, result: str = "won", price: str = "1.8"):
    return {
        "event": f"A vs B {day}",
        "prediction": "A",
        "result": result,
        "best_price": price,
        "pick_time": f"2026-01-{day:02d}T10:00:00Z",
        "start_time": f"2026-01-{day:02d}T20:00:00Z",
        "feature_timestamp": f"2026-01-{day:02d}T09:00:00Z",
    }


class BacktestEngineTests(unittest.TestCase):
    def test_audit_flags_future_feature_timestamp(self) -> None:
        row = _row(1)
        row["feature_timestamp"] = "2026-01-01T11:00:00Z"
        flags = audit_row_for_leakage(row)
        self.assertIn("feature_timestamp_after_pick_time", flags)

    def test_audit_flags_pick_after_start(self) -> None:
        row = _row(1)
        row["pick_time"] = "2026-01-01T21:00:00Z"
        flags = audit_row_for_leakage(row)
        self.assertIn("pick_after_event_start", flags)

    def test_backtest_splits_time_ordered_rows(self) -> None:
        rows = [_row(day, "won" if day % 2 else "lost") for day in range(1, 11)]
        report = run_backtest_rows(rows, BacktestPolicy(train_fraction=0.6, min_train_rows=1, min_test_rows=1, profit_goal_min_finished=1))
        self.assertEqual(report.raw_rows, 10)
        self.assertEqual(report.usable_rows, 10)
        self.assertEqual(report.train_rows, 6)
        self.assertEqual(report.test_rows, 4)
        self.assertIn(report.status, {"PASS", "WATCH"})

    def test_backtest_rejects_leakage_rows(self) -> None:
        rows = [_row(1), _row(2)]
        rows[1]["closing_odds_as_model_input"] = "true"
        report = run_backtest_rows(rows, BacktestPolicy(min_train_rows=1, min_test_rows=1, profit_goal_min_finished=1))
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(report.rejected_rows, 1)
        self.assertIn("closing_odds_as_model_input", report.leakage_flags)

    def test_backtest_allows_missing_feature_timestamp_by_default(self) -> None:
        row = _row(1)
        row.pop("feature_timestamp")
        flags = audit_row_for_leakage(row)
        self.assertNotIn("missing_feature_timestamp", flags)
        strict_flags = audit_row_for_leakage(row, BacktestPolicy(allow_missing_feature_timestamp=False))
        self.assertIn("missing_feature_timestamp", strict_flags)


if __name__ == "__main__":
    unittest.main()

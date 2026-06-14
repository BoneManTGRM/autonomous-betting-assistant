from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.backtest_engine import BacktestPolicy, run_backtest_csv, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a time-aware historical backtest with anti-leakage checks.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/backtest_report.json"))
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--min-train-rows", type=int, default=20)
    parser.add_argument("--min-test-rows", type=int, default=20)
    parser.add_argument("--profit-min-finished", type=int, default=50)
    parser.add_argument("--allow-missing-pick-time", action="store_true")
    parser.add_argument("--allow-missing-event-start", action="store_true")
    parser.add_argument("--require-feature-timestamp", action="store_true")
    args = parser.parse_args()

    policy = BacktestPolicy(
        train_fraction=args.train_fraction,
        min_train_rows=args.min_train_rows,
        min_test_rows=args.min_test_rows,
        profit_goal_min_finished=args.profit_min_finished,
        allow_missing_pick_time=args.allow_missing_pick_time,
        allow_missing_event_start=args.allow_missing_event_start,
        allow_missing_feature_timestamp=not args.require_feature_timestamp,
    )
    report = run_backtest_csv(args.input_csv, policy=policy)
    write_report(report, args.output)
    print(report)
    return 0 if report.status != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())

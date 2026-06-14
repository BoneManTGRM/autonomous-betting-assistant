from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.walk_forward_backtest import run_walk_forward_backtest_csv, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run time-ordered walk-forward backtesting.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/walk_forward_report.json"))
    parser.add_argument("--train-size", type=int, default=100)
    parser.add_argument("--test-size", type=int, default=25)
    parser.add_argument("--step-size", type=int, default=None)
    parser.add_argument("--min-selected-per-fold", type=int, default=1)
    args = parser.parse_args()

    report = run_walk_forward_backtest_csv(
        args.input_csv,
        train_size=args.train_size,
        test_size=args.test_size,
        step_size=args.step_size,
        min_selected_per_fold=args.min_selected_per_fold,
    )
    write_report(report, args.output)
    print(report)
    return 0 if report.status != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.selection_optimizer import optimize_selection_csv, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize betting selection filters on a time-ordered train/test split.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/selection_optimizer_report.json"))
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--min-train-selected", type=int, default=20)
    parser.add_argument("--min-test-selected", type=int, default=20)
    args = parser.parse_args()

    report = optimize_selection_csv(
        args.input_csv,
        train_fraction=args.train_fraction,
        min_train_selected=args.min_train_selected,
        min_test_selected=args.min_test_selected,
    )
    write_report(report, args.output)
    print(report)
    return 0 if report.status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

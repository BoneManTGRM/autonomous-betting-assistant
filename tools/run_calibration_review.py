from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.calibration_review import review_calibration_csv, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Review calibration quality from graded predictions.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/calibration_review_report.json"))
    parser.add_argument("--min-records", type=int, default=10)
    parser.add_argument("--gap-threshold", type=float, default=0.08)
    args = parser.parse_args()

    report = review_calibration_csv(args.input_csv, min_records=args.min_records, gap_threshold=args.gap_threshold)
    write_report(report, args.output)
    print("Calibration review complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

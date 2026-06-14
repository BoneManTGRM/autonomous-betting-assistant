from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from autonomous_betting_agent.accuracy_calibration import (
    apply_calibration,
    read_csv_rows,
    write_csv_rows,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply historical probability calibration to prediction rows.")
    parser.add_argument("predictions_csv", type=Path)
    parser.add_argument("history_csv", type=Path, help="Historical graded rows with model_probability and result columns")
    parser.add_argument("--output", type=Path, default=Path("data/predictions_calibrated.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("data/accuracy_calibration_report.json"))
    parser.add_argument("--bucket-size", type=float, default=0.05)
    parser.add_argument("--min-bucket-samples", type=int, default=20)
    parser.add_argument("--shrinkage-strength", type=float, default=25.0)
    parser.add_argument("--min-scope-samples", type=int, default=50)
    args = parser.parse_args()

    predictions = read_csv_rows(args.predictions_csv)
    history = read_csv_rows(args.history_csv)
    calibrated, report = apply_calibration(
        predictions,
        history,
        bucket_size=args.bucket_size,
        min_bucket_samples=args.min_bucket_samples,
        shrinkage_strength=args.shrinkage_strength,
        min_scope_samples=args.min_scope_samples,
    )
    write_csv_rows(calibrated, args.output)
    write_report(replace(report, output_csv=str(args.output)), args.report_output)
    print(f"Saved {len(calibrated)} calibrated prediction row(s) to {args.output}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

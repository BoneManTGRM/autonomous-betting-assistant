from __future__ import annotations

import argparse
import json
from pathlib import Path

from autonomous_betting_agent.calibration_review import read_csv_rows, review_calibration_rows
from autonomous_betting_agent.report_proof import attach_proof_audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Review calibration quality from graded predictions.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/calibration_review_report.json"))
    parser.add_argument("--min-records", type=int, default=10)
    parser.add_argument("--gap-threshold", type=float, default=0.08)
    args = parser.parse_args()

    rows = read_csv_rows(args.input_csv)
    report = review_calibration_rows(rows, min_records=args.min_records, gap_threshold=args.gap_threshold)
    report = attach_proof_audit(report, rows, report_name="calibration_review")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Calibration review complete")
    print(f"Saved calibration report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

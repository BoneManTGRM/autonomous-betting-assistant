from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.line_movement_model import (
    enrich_line_movement_rows,
    read_csv_rows,
    summarize_line_movement,
    write_csv_rows,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich picks with line movement and historical market-support signals.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--history-csv", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("data/predictions_with_line_movement.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("data/line_movement_report.json"))
    parser.add_argument("--min-profile-samples", type=int, default=10)
    args = parser.parse_args()

    rows = read_csv_rows(args.input_csv)
    history = read_csv_rows(args.history_csv) if args.history_csv else []
    enriched = enrich_line_movement_rows(rows, history, min_profile_samples=args.min_profile_samples)
    write_csv_rows(enriched, args.output)
    report = summarize_line_movement(enriched, history, output_csv=str(args.output))
    write_report(report, args.report_output)
    print(f"Saved {len(enriched)} line-movement row(s) to {args.output}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from autonomous_betting_agent.prediction_validator import (
    ValidationPolicy,
    read_csv_rows,
    validate_prediction_rows,
    write_csv_rows,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Predictor Pro prediction CSV before scoring.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/predictions_validated.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("data/prediction_validation_report.json"))
    parser.add_argument("--allow-missing-pick-time", action="store_true")
    parser.add_argument("--allow-missing-start-time", action="store_true")
    parser.add_argument("--allow-missing-odds", action="store_true")
    parser.add_argument("--allow-started-games", action="store_true")
    parser.add_argument("--min-bookmaker-count", type=int, default=None)
    parser.add_argument("--min-data-quality", type=float, default=None)
    parser.add_argument("--fail-on-watch", action="store_true")
    args = parser.parse_args()

    policy = ValidationPolicy(
        require_pick_time=not args.allow_missing_pick_time,
        require_start_time=not args.allow_missing_start_time,
        require_price=not args.allow_missing_odds,
        reject_started_games=not args.allow_started_games,
        min_bookmaker_count=args.min_bookmaker_count,
        min_data_quality=args.min_data_quality,
    )
    rows = read_csv_rows(args.input_csv)
    validated, report = validate_prediction_rows(rows, policy=policy)
    write_csv_rows(validated, args.output)
    write_report(replace(report, output_csv=str(args.output), issues_json=str(args.report_output)), args.report_output)
    print(f"Validation status: {report.status}")
    print(report)
    if report.status == "FAIL" or (args.fail_on_watch and report.status == "WATCH"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

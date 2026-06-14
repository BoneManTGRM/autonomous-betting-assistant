from __future__ import annotations

import argparse
import json
from pathlib import Path

from autonomous_betting_agent.learning import GradedPrediction, fit_probability_calibrator, parse_graded_csv


def dedupe_rows(rows: list[GradedPrediction]) -> list[GradedPrediction]:
    seen: set[tuple[str, str, str, int]] = set()
    unique: list[GradedPrediction] = []
    for row in rows:
        key = (row.event_name.strip().lower(), row.predicted_side.strip().lower(), row.actual_side.strip().lower(), row.outcome)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="Train probability calibration from a graded prediction CSV.")
    parser.add_argument("results_csv", type=Path, help="CSV containing past predictions and final results")
    parser.add_argument("--output", type=Path, default=Path("learned_state.json"), help="Where to save the learned calibration state")
    parser.add_argument("--epochs", type=int, default=2500)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--l2", type=float, default=0.01)
    parser.add_argument("--min-events", type=int, default=5)
    parser.add_argument("--keep-duplicates", action="store_true", help="Keep duplicate graded rows instead of training on unique events")
    args = parser.parse_args()

    parsed_rows = parse_graded_csv(args.results_csv)
    rows = parsed_rows if args.keep_duplicates else dedupe_rows(parsed_rows)
    if len(rows) < args.min_events:
        parser.error(f"Found {len(rows)} usable graded rows; need at least {args.min_events}.")
        return 2

    calibrator = fit_probability_calibrator(
        rows,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
        min_events=args.min_events,
        source=str(args.results_csv),
    )
    calibrator.notes.append(f"Parsed {len(parsed_rows)} usable graded rows; trained on {len(rows)} rows.")
    calibrator.save(args.output)

    print(json.dumps(calibrator.to_dict(), indent=2, sort_keys=True))
    print(f"Saved learned state to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

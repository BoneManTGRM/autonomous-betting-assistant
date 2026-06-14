from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from autonomous_betting_agent.ensemble_agreement import (
    EnsemblePolicy,
    apply_ensemble_scoring,
    read_csv_rows,
    summarize_ensemble,
    write_csv_rows,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score picks by ensemble agreement across model, market and data-quality signals.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/predictions_with_ensemble.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("data/ensemble_report.json"))
    parser.add_argument("--accept-score", type=float, default=70.0)
    parser.add_argument("--watch-score", type=float, default=50.0)
    parser.add_argument("--min-probability", type=float, default=0.56)
    parser.add_argument("--min-edge", type=float, default=0.02)
    parser.add_argument("--min-data-quality", type=float, default=70.0)
    parser.add_argument("--min-bookmaker-count", type=int, default=3)
    args = parser.parse_args()

    policy = EnsemblePolicy(
        min_probability=args.min_probability,
        min_edge=args.min_edge,
        min_data_quality=args.min_data_quality,
        min_bookmaker_count=args.min_bookmaker_count,
        accept_score=args.accept_score,
        watch_score=args.watch_score,
    )
    rows = read_csv_rows(args.input_csv)
    scored = apply_ensemble_scoring(rows, policy=policy)
    write_csv_rows(scored, args.output)
    report = summarize_ensemble(scored, output_csv=str(args.output))
    write_report(replace(report, output_csv=str(args.output)), args.report_output)
    print(f"Saved {len(scored)} ensemble-scored row(s) to {args.output}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

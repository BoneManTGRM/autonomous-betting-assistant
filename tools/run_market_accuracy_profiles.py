from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.market_accuracy_profiles import (
    enrich_with_market_profiles,
    read_csv_rows,
    summarize_profiles,
    write_csv_rows,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich picks with sport/market-specific historical accuracy profiles.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("history_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/predictions_with_market_profiles.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("data/market_accuracy_profiles_report.json"))
    parser.add_argument("--min-samples", type=int, default=10)
    args = parser.parse_args()

    rows = read_csv_rows(args.input_csv)
    history = read_csv_rows(args.history_csv)
    enriched = enrich_with_market_profiles(rows, history, min_samples=args.min_samples)
    write_csv_rows(enriched, args.output)
    report = summarize_profiles(enriched, history, output_csv=str(args.output))
    write_report(report, args.report_output)
    print(f"Saved {len(enriched)} market-profile row(s) to {args.output}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

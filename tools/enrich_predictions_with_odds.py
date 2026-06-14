from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.odds_clv import (
    enrich_predictions_with_odds,
    read_csv_rows,
    summarize_odds_enrichment,
    write_csv_rows,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich prediction rows with odds, closing odds and CLV from an odds CSV.")
    parser.add_argument("predictions_csv", type=Path)
    parser.add_argument("odds_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/predictions_with_odds_clv.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("data/odds_clv_report.json"))
    parser.add_argument("--source", default="odds_csv")
    args = parser.parse_args()

    predictions = read_csv_rows(args.predictions_csv)
    odds = read_csv_rows(args.odds_csv)
    enriched = enrich_predictions_with_odds(predictions, odds, source=args.source)
    write_csv_rows(enriched, args.output)
    report = summarize_odds_enrichment(enriched, output_csv=str(args.output))
    write_report(report, args.report_output)
    print(f"Saved {len(enriched)} odds-enriched prediction row(s) to {args.output}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

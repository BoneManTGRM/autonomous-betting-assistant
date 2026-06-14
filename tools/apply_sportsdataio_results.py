from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.sportsdataio_results import (
    enrich_predictions_with_results,
    read_csv_rows,
    write_csv_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich prediction CSV rows with canonical SportsDataIO game results.")
    parser.add_argument("predictions_csv", type=Path)
    parser.add_argument("canonical_games_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/predictions_with_sportsdataio_results.csv"))
    args = parser.parse_args()

    predictions = read_csv_rows(args.predictions_csv)
    games = read_csv_rows(args.canonical_games_csv)
    enriched = enrich_predictions_with_results(predictions, games)
    write_csv_rows(enriched, args.output)

    counts: dict[str, int] = {}
    for row in enriched:
        status = str(row.get("sdio_result_match_status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    print(f"Saved {len(enriched)} enriched prediction row(s) to {args.output}")
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.sportsdataio_player_features import (
    build_player_features,
    read_csv_rows,
    write_player_features,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build model-ready player features from a SportsDataIO stats CSV.")
    parser.add_argument("input_csv", type=Path, help="Flattened or canonical SportsDataIO player stats CSV")
    parser.add_argument("--sport", default="", help="Optional sport label to add to output rows")
    parser.add_argument("--source", default="SportsDataIO")
    parser.add_argument("--output", type=Path, default=Path("data/sportsdataio_player_features.csv"))
    args = parser.parse_args()

    rows = read_csv_rows(args.input_csv)
    features = build_player_features(rows, sport=args.sport, source=args.source)
    write_player_features(features, args.output)

    ready = sum(1 for row in features if row.get("feature_ready") == "true")
    print(f"Saved {len(features)} player feature row(s) to {args.output}")
    print({"feature_ready": ready, "feature_not_ready": len(features) - ready})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

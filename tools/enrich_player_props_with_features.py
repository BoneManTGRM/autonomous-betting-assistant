from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.player_prop_features import (
    enrich_props_with_player_features,
    read_csv_rows,
    write_csv_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Join player prop rows with SportsDataIO player feature rows.")
    parser.add_argument("props_csv", type=Path)
    parser.add_argument("features_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/player_props_enriched_with_features.csv"))
    args = parser.parse_args()

    props = read_csv_rows(args.props_csv)
    features = read_csv_rows(args.features_csv)
    enriched = enrich_props_with_player_features(props, features)
    write_csv_rows(enriched, args.output)

    counts: dict[str, int] = {}
    for row in enriched:
        status = str(row.get("feature_match_status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    print(f"Saved {len(enriched)} feature-enriched prop row(s) to {args.output}")
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

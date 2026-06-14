from __future__ import annotations

import argparse
import os
from pathlib import Path

from autonomous_betting_agent.live_odds import scan_market
from autonomous_betting_agent.market_snapshots import append_snapshot_csv, latest_snapshot_with_movement, summaries_to_snapshot_frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture The Odds API market snapshots for line-movement tracking.")
    parser.add_argument("sport_key", help="The Odds API sport key, for example soccer_epl, basketball_nba, baseball_mlb.")
    parser.add_argument("--api-key", default="", help="The Odds API key. If omitted, THE_ODDS_API_KEY is used.")
    parser.add_argument("--regions", default="us,us2,uk,eu")
    parser.add_argument("--max-events", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("data/market_snapshots.csv"))
    parser.add_argument("--latest-output", type=Path, default=Path("data/latest_market_movement.csv"))
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("THE_ODDS_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing API key. Pass --api-key or set THE_ODDS_API_KEY.")

    summaries = scan_market(api_key, sport_key=args.sport_key, regions=args.regions, max_events=args.max_events)
    snapshot = summaries_to_snapshot_frame(summaries)
    combined = append_snapshot_csv(snapshot, args.output)
    latest = latest_snapshot_with_movement(combined)
    args.latest_output.parent.mkdir(parents=True, exist_ok=True)
    latest.to_csv(args.latest_output, index=False)
    print(f"Saved {len(snapshot)} snapshot rows to {args.output}")
    print(f"Saved latest movement rows to {args.latest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

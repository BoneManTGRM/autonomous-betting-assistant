from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.sportsdataio import (
    DEFAULT_KEY_ENV,
    SportsDataIOClient,
    SportsDataIOConfig,
    payload_row_count,
    write_json_payload,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a SportsDataIO endpoint and save the raw JSON payload.")
    parser.add_argument("endpoint", help="Endpoint path after /v3/{sport}/{subfeed}/json/, for example ScoresByDate/2026-JAN-15")
    parser.add_argument("--sport", default="nfl", help="League/sport slug, for example nfl, mlb, nba, nhl, soccer")
    parser.add_argument("--subfeed", default="scores", help="SportsDataIO subfeed, commonly scores, stats, odds or projections")
    parser.add_argument("--version", default="v3")
    parser.add_argument("--format", default="json", dest="fmt")
    parser.add_argument("--api-key", default=None, help=f"SportsDataIO key. If omitted, {DEFAULT_KEY_ENV} is used.")
    parser.add_argument("--auth-mode", choices=["header", "query"], default="header")
    parser.add_argument("--output", type=Path, default=Path("data/sportsdataio_raw.json"))
    args = parser.parse_args()

    if args.api_key:
        config = SportsDataIOConfig(
            api_key=args.api_key,
            sport=args.sport,
            subfeed=args.subfeed,
            version=args.version,
            fmt=args.fmt,
            auth_mode=args.auth_mode,
        )
    else:
        config = SportsDataIOConfig.from_env(
            sport=args.sport,
            subfeed=args.subfeed,
            version=args.version,
            fmt=args.fmt,
            auth_mode=args.auth_mode,
        )

    client = SportsDataIOClient(config)
    payload = client.raw_endpoint(args.endpoint, sport=args.sport, subfeed=args.subfeed)
    write_json_payload(payload, args.output)
    print(f"Saved {payload_row_count(payload)} SportsDataIO row(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

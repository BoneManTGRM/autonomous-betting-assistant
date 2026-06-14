from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.sportsdataio import (
    DEFAULT_KEY_ENV,
    SportsDataIOClient,
    SportsDataIOConfig,
    payload_row_count,
    payload_to_records,
    write_csv_records,
    write_json_payload,
)
from autonomous_betting_agent.sportsdataio_normalize import write_normalized_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a SportsDataIO endpoint and save JSON, flattened CSV and optional canonical CSV outputs.")
    parser.add_argument("endpoint", help="Endpoint path after /v3/{sport}/{subfeed}/json/, for example ScoresByDate/2026-JAN-15")
    parser.add_argument("--sport", default="nfl", help="League/sport slug, for example nfl, mlb, nba, nhl, soccer")
    parser.add_argument("--subfeed", default="scores", help="SportsDataIO subfeed, commonly scores, stats, odds or projections")
    parser.add_argument("--version", default="v3")
    parser.add_argument("--format", default="json", dest="fmt")
    parser.add_argument("--api-key", default=None, help=f"SportsDataIO key. If omitted, {DEFAULT_KEY_ENV} is used.")
    parser.add_argument("--auth-mode", choices=["header", "query"], default="header")
    parser.add_argument("--output", type=Path, default=Path("data/sportsdataio_raw.json"))
    parser.add_argument("--csv-output", type=Path, default=None, help="Optional flattened CSV output path")
    parser.add_argument("--canonical-output", type=Path, default=None, help="Optional canonical CSV output for known dataset types")
    parser.add_argument("--dataset-type", choices=["auto", "games", "players", "teams"], default="auto")
    parser.add_argument("--record-key", default=None, help="Optional top-level JSON key to flatten when payload is an object containing lists")
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
    records = payload_to_records(payload, record_key=args.record_key)
    message = f"Saved {payload_row_count(payload)} SportsDataIO row(s) to {args.output}"
    if args.csv_output:
        write_csv_records(records, args.csv_output)
        message += f" and flattened CSV to {args.csv_output}"
    if args.canonical_output:
        normalized = write_normalized_csv(records, args.canonical_output, dataset_type=args.dataset_type, sport=args.sport)
        message += f" and {len(normalized)} canonical row(s) to {args.canonical_output}"
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

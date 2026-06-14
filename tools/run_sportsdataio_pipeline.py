from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.sportsdataio import SportsDataIOClient, SportsDataIOConfig
from autonomous_betting_agent.sportsdataio_pipeline import run_sportsdataio_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full SportsDataIO ingestion and enrichment pipeline.")
    parser.add_argument("--sport", default="nfl")
    parser.add_argument("--games-endpoint", default=None, help="SportsDataIO scores endpoint, for example ScoresByDate/2026-JAN-15")
    parser.add_argument("--player-stats-endpoint", default=None, help="SportsDataIO stats endpoint, for example PlayerSeasonStats/2026")
    parser.add_argument("--predictions-csv", type=Path, default=None)
    parser.add_argument("--player-props-csv", type=Path, default=None)
    parser.add_argument("--existing-canonical-games-csv", type=Path, default=None)
    parser.add_argument("--existing-player-features-csv", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("data/sportsdataio_pipeline"))
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--auth-mode", choices=["header", "query"], default="header")
    parser.add_argument("--include-watch", action="store_true")
    args = parser.parse_args()

    client = None
    if args.games_endpoint or args.player_stats_endpoint:
        if args.api_key:
            config = SportsDataIOConfig(api_key=args.api_key, sport=args.sport, auth_mode=args.auth_mode)
        else:
            config = SportsDataIOConfig.from_env(sport=args.sport, auth_mode=args.auth_mode)
        client = SportsDataIOClient(config)

    report = run_sportsdataio_pipeline(
        client=client,
        sport=args.sport,
        games_endpoint=args.games_endpoint,
        player_stats_endpoint=args.player_stats_endpoint,
        predictions_csv=args.predictions_csv,
        player_props_csv=args.player_props_csv,
        existing_canonical_games_csv=args.existing_canonical_games_csv,
        existing_player_features_csv=args.existing_player_features_csv,
        output_dir=args.output_dir,
        include_watch=args.include_watch,
    )
    print("SportsDataIO pipeline complete")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

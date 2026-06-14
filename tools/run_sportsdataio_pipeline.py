from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.sportsdataio import SportsDataIOClient, SportsDataIOConfig
from autonomous_betting_agent.sportsdataio_pipeline import run_sportsdataio_pipeline
from autonomous_betting_agent.sportsdataio_quality import quality_gate_allows


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
    parser.add_argument("--skip-profit-goal-review", action="store_true")
    parser.add_argument("--profit-min-finished", type=int, default=200)
    parser.add_argument("--allow-missing-clv", action="store_true")
    parser.add_argument(
        "--minimum-quality-status",
        choices=["PASS", "WATCH", "FAIL"],
        default="FAIL",
        help="Exit non-zero if the quality gate is below this status. Use WATCH to block FAIL, or PASS to block WATCH/FAIL.",
    )
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
        run_profit_goal_review=not args.skip_profit_goal_review,
        profit_goal_min_finished=args.profit_min_finished,
        allow_missing_clv=args.allow_missing_clv,
    )
    print("SportsDataIO pipeline complete")
    print(report)
    if not quality_gate_allows(report.quality_gate, minimum_status=args.minimum_quality_status):
        status = "missing" if report.quality_gate is None else report.quality_gate.status
        print(f"Quality gate blocked continuation: status={status}, required={args.minimum_quality_status}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

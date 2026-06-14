from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.bankroll_exposure import (
    BankrollPolicy,
    apply_bankroll_exposure,
    read_csv_rows,
    summarize_bankroll,
    write_csv_rows,
    write_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply bankroll sizing and exposure controls to scored picks.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/predictions_with_bankroll.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("data/bankroll_report.json"))
    parser.add_argument("--bankroll-units", type=float, default=100.0)
    parser.add_argument("--max-stake-per-pick", type=float, default=2.0)
    parser.add_argument("--max-daily-exposure", type=float, default=8.0)
    parser.add_argument("--max-sport-exposure", type=float, default=4.0)
    parser.add_argument("--max-league-exposure", type=float, default=3.0)
    parser.add_argument("--max-market-exposure", type=float, default=3.0)
    parser.add_argument("--max-team-exposure", type=float, default=2.0)
    parser.add_argument("--kelly-fraction", type=float, default=0.25)
    args = parser.parse_args()

    policy = BankrollPolicy(
        bankroll_units=args.bankroll_units,
        max_stake_per_pick_units=args.max_stake_per_pick,
        max_daily_exposure_units=args.max_daily_exposure,
        max_sport_exposure_units=args.max_sport_exposure,
        max_league_exposure_units=args.max_league_exposure,
        max_market_exposure_units=args.max_market_exposure,
        max_team_exposure_units=args.max_team_exposure,
        kelly_fraction=args.kelly_fraction,
    )
    rows = read_csv_rows(args.input_csv)
    sized = apply_bankroll_exposure(rows, policy=policy)
    write_csv_rows(sized, args.output)
    report = summarize_bankroll(sized, output_csv=str(args.output))
    write_report(report, args.report_output)
    print(f"Saved {len(sized)} bankroll-managed row(s) to {args.output}")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

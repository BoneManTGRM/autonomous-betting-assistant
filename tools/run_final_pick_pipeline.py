from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.bankroll_exposure import BankrollPolicy
from autonomous_betting_agent.final_pick_pipeline import run_final_pick_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the final pick pipeline and split bets, watchlist and rejects.")
    parser.add_argument("predictions_csv", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/final_pick_pipeline"))
    parser.add_argument("--calibration-history-csv", type=Path, default=None)
    parser.add_argument("--line-movement-history-csv", type=Path, default=None)
    parser.add_argument("--market-profile-history-csv", type=Path, default=None)
    parser.add_argument("--bankroll-units", type=float, default=100.0)
    parser.add_argument("--max-stake-per-pick", type=float, default=2.0)
    parser.add_argument("--max-daily-exposure", type=float, default=8.0)
    args = parser.parse_args()

    report = run_final_pick_pipeline(
        predictions_csv=args.predictions_csv,
        output_dir=args.output_dir,
        calibration_history_csv=args.calibration_history_csv,
        line_movement_history_csv=args.line_movement_history_csv,
        market_profile_history_csv=args.market_profile_history_csv,
        bankroll_policy=BankrollPolicy(
            bankroll_units=args.bankroll_units,
            max_stake_per_pick_units=args.max_stake_per_pick,
            max_daily_exposure_units=args.max_daily_exposure,
        ),
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from autonomous_betting_agent.profit_goal import ProfitGoalPolicy, review_profit_goal_csv, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a prediction CSV meets the profitable 70 percent goal.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/profit_goal_report.json"))
    parser.add_argument("--target-win-rate", type=float, default=0.70)
    parser.add_argument("--win-rate-tolerance", type=float, default=0.01)
    parser.add_argument("--min-average-odds", type=float, default=1.43)
    parser.add_argument("--min-finished", type=int, default=200)
    parser.add_argument("--allow-missing-clv", action="store_true")
    args = parser.parse_args()

    policy = ProfitGoalPolicy(
        target_win_rate=args.target_win_rate,
        win_rate_tolerance=args.win_rate_tolerance,
        min_average_odds=args.min_average_odds,
        min_finished=args.min_finished,
        require_positive_clv=not args.allow_missing_clv,
    )
    report = review_profit_goal_csv(args.input_csv, policy=policy)
    write_report(report, args.output)
    print(asdict(report))
    print(f"Saved profit goal report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from autonomous_betting_agent.profit_goal import ProfitGoalPolicy, read_csv_rows, review_profit_goal_rows
from autonomous_betting_agent.report_proof import attach_proof_audit


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
    rows = read_csv_rows(args.input_csv)
    report = review_profit_goal_rows(rows, policy=policy)
    report_payload = attach_proof_audit(asdict(report), rows, report_name="profit_goal_review")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report_payload, indent=2, sort_keys=True))
    print(f"Saved profit goal report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

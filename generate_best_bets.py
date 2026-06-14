from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.best_bets import apply_best_bet_layer, rank_best_bets
from autonomous_betting_agent.deep_analysis import merge_latest_movement


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a disciplined ARA best-bet shortlist from prediction rows.")
    parser.add_argument("input_csv", type=Path, help="Prediction CSV to rank.")
    parser.add_argument("--movement-csv", type=Path, default=None, help="Optional latest_market_movement.csv file.")
    parser.add_argument("--output", type=Path, default=Path("data/best_bet_ranked.csv"), help="Full ranked output CSV.")
    parser.add_argument("--shortlist-output", type=Path, default=Path("data/best_bet_shortlist.csv"), help="Qualified-only shortlist CSV.")
    parser.add_argument("--top-n", type=int, default=25, help="Maximum shortlist rows to write.")
    parser.add_argument("--include-watch", action="store_true", help="Include WATCH/TRACK rows in the shortlist for review.")
    args = parser.parse_args()

    predictions = pd.read_csv(args.input_csv)
    movement = None
    if args.movement_csv and args.movement_csv.exists():
        movement = pd.read_csv(args.movement_csv)

    ranked_input = predictions
    if movement is not None:
        ranked_input = merge_latest_movement(predictions, movement)

    full = apply_best_bet_layer(ranked_input)
    shortlist = rank_best_bets(predictions, movement, top_n=args.top_n, include_watch=args.include_watch)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.shortlist_output.parent.mkdir(parents=True, exist_ok=True)
    full.to_csv(args.output, index=False)
    shortlist.to_csv(args.shortlist_output, index=False)
    print(f"Saved full best-bet ranking to {args.output}")
    print(f"Saved shortlist to {args.shortlist_output}")
    print("Qualified rows:", int(shortlist["aba_best_bet_status"].astype(str).str.startswith("QUALIFIED").sum()) if not shortlist.empty else 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

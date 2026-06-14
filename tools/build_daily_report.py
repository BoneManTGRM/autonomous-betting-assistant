from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.reporting import build_daily_markdown_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a human-readable daily Markdown report from final pipeline CSV outputs.")
    parser.add_argument("--final-bets-csv", type=Path, required=True)
    parser.add_argument("--watchlist-csv", type=Path, required=True)
    parser.add_argument("--rejected-picks-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/daily_summary.md"))
    parser.add_argument("--title", default="Daily Betting Agent Summary")
    args = parser.parse_args()

    build_daily_markdown_report(
        final_bets_csv=args.final_bets_csv,
        watchlist_csv=args.watchlist_csv,
        rejected_picks_csv=args.rejected_picks_csv,
        output_md=args.output,
        title=args.title,
    )
    print(f"Saved Markdown report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

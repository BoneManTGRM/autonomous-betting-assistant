from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.pick_store import summarize_store, write_history_csv, write_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize or export the local pick memory database.")
    parser.add_argument("--db-path", type=Path, default=Path("data/picks.sqlite"))
    parser.add_argument("--summary-output", type=Path, default=Path("data/pick_store_summary.json"))
    parser.add_argument("--history-output", type=Path, default=None)
    args = parser.parse_args()

    summary = summarize_store(args.db_path)
    write_summary(summary, args.summary_output)
    if args.history_output:
        write_history_csv(args.db_path, args.history_output)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

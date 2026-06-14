from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.result_reconciler import reconcile_results


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile unfinished picks in the SQLite store against canonical final games.")
    parser.add_argument("--db-path", type=Path, default=Path("data/picks.sqlite"))
    parser.add_argument("--canonical-games-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/reconcile_report.json"))
    args = parser.parse_args()

    report = reconcile_results(db_path=args.db_path, canonical_games_csv=args.canonical_games_csv, output_json=args.output)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

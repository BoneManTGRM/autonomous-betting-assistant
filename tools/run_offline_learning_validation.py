"""Read an explicit JSON dataset and print a non-promoting offline report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autonomous_betting_agent.offline_learning_validation import run_offline_validation


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Do not let JSON last-write-wins semantics hide conflicting evidence."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline observation-only calibration experiment. Never writes learning state.")
    parser.add_argument("input_json", type=Path, help="Explicit verified records; no automatic ledger discovery")
    parser.add_argument("--train-before", required=True)
    parser.add_argument("--holdout-from", required=True)
    parser.add_argument("--evaluation-as-of", required=True)
    args = parser.parse_args(argv)
    try:
        rows = json.loads(args.input_json.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(rows, list):
            raise ValueError("input JSON must be a list of verified observations")
        report = run_offline_validation(rows, train_before=args.train_before, holdout_from=args.holdout_from,
                                        evaluation_as_of=args.evaluation_as_of)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "REVIEW_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())

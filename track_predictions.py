from __future__ import annotations

import argparse
import json
from pathlib import Path

from autonomous_betting_agent.report_proof import attach_proof_audit
from autonomous_betting_agent.tracking import read_prediction_csv, summarize_tracking, write_ledger_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Track prediction quality, edge, profit/loss, CLV, confidence buckets, and sport performance.")
    parser.add_argument("predictions_csv", type=Path, help="CSV containing predictions, odds, probabilities, and optional final results")
    parser.add_argument("--ledger-output", type=Path, default=Path("prediction_ledger_enriched.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("prediction_report.json"))
    args = parser.parse_args()

    rows = read_prediction_csv(args.predictions_csv)
    report = summarize_tracking(rows)
    report_payload = attach_proof_audit(report.to_dict(), rows, report_name="prediction_tracking")

    write_ledger_csv(rows, args.ledger_output)
    args.report_output.write_text(json.dumps(report_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(report_payload, indent=2, sort_keys=True))
    print(f"Saved enriched ledger to {args.ledger_output}")
    print(f"Saved report to {args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

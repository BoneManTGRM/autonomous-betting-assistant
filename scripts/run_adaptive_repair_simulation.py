"""Run ABA Adaptive Repair Phase 3A simulation-only runner scans."""

from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.adaptive_repair_runner import (
    run_adaptive_repair_scan,
    run_adaptive_repair_scan_from_csv,
    runner_report_to_markdown,
    save_runner_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ABA Adaptive Repair Runner scan.")
    parser.add_argument("csv_path", nargs="?", help="Optional path to a graded CSV/export file")
    parser.add_argument("--system-scan", action="store_true", help="Scan available local system sources")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    parser.add_argument("--output", "-o", help="Optional path to save the Markdown or JSON report")
    parser.add_argument("--save-run", action="store_true", help="Persist the runner scan under data/adaptive_repair/simulation_runs/")
    parser.add_argument(
        "--fail-below-quality",
        type=float,
        default=None,
        help="Exit with status 2 if the data-quality score is below this threshold",
    )
    args = parser.parse_args()

    if args.csv_path:
        report = run_adaptive_repair_scan_from_csv(Path(args.csv_path), include_system_sources=args.system_scan)
    else:
        report = run_adaptive_repair_scan(include_system_sources=True)

    output = report.to_json() if args.json else runner_report_to_markdown(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)

    if args.save_run:
        save_runner_report(report)

    quality_score = float(report.diagnostics.get("data_quality", {}).get("score", 0.0) or 0.0)
    if args.fail_below_quality is not None and quality_score < args.fail_below_quality:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

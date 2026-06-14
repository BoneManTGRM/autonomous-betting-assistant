from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.daily_runner import run_daily_agent


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily agent once. Automation is disabled unless explicitly toggled on.")
    parser.add_argument("predictions_csv", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("data/daily"))
    parser.add_argument("--db-path", type=Path, default=Path("data/picks.sqlite"))
    parser.add_argument("--calibration-history-csv", type=Path, default=None)
    parser.add_argument("--line-movement-history-csv", type=Path, default=None)
    parser.add_argument("--market-profile-history-csv", type=Path, default=None)
    parser.add_argument("--model-version", default="")
    parser.add_argument("--pipeline-version", default="")
    parser.add_argument("--run-mode", choices=["manual", "automated_daily"], default="manual")
    parser.add_argument("--enable-automated-daily", action="store_true", help="Required for run-mode automated_daily. Manual mode is the default.")
    args = parser.parse_args()

    report = run_daily_agent(
        predictions_csv=args.predictions_csv,
        output_root=args.output_root,
        db_path=args.db_path,
        calibration_history_csv=args.calibration_history_csv,
        line_movement_history_csv=args.line_movement_history_csv,
        market_profile_history_csv=args.market_profile_history_csv,
        model_version=args.model_version,
        pipeline_version=args.pipeline_version,
        automated_daily_enabled=args.enable_automated_daily,
        run_mode=args.run_mode,
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

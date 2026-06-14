from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .bankroll_exposure import BankrollPolicy
from .final_pick_pipeline import run_final_pick_pipeline
from .pick_store import create_run, record_pick_rows, summarize_store


@dataclass(frozen=True)
class DailyRunnerReport:
    run_id: str
    run_mode: str
    automated_daily_enabled: bool
    predictions_csv: str
    output_dir: str
    db_path: str
    final_bets: int
    watchlist: int
    rejected: int
    stored_rows: int
    store_pick_count: int
    report_json: str
    warnings: list[str]
    notes: list[str]


def _date_slug() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    import csv

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run_daily_agent(
    *,
    predictions_csv: str | Path,
    output_root: str | Path = "data/daily",
    db_path: str | Path = "data/picks.sqlite",
    calibration_history_csv: str | Path | None = None,
    line_movement_history_csv: str | Path | None = None,
    market_profile_history_csv: str | Path | None = None,
    model_version: str = "",
    pipeline_version: str = "",
    automated_daily_enabled: bool = False,
    run_mode: str = "manual",
    bankroll_policy: BankrollPolicy = BankrollPolicy(),
) -> DailyRunnerReport:
    """Run the daily agent once.

    Automation is intentionally opt-in. Passing run_mode='automated_daily' without
    automated_daily_enabled=True raises an error so normal users can run the same
    pipeline manually without accidentally enabling scheduled behavior.
    """
    if run_mode == "automated_daily" and not automated_daily_enabled:
        raise ValueError("automated_daily mode requires automated_daily_enabled=True")
    if run_mode not in {"manual", "automated_daily"}:
        raise ValueError("run_mode must be 'manual' or 'automated_daily'")

    output_dir = Path(output_root) / _date_slug()
    output_dir.mkdir(parents=True, exist_ok=True)
    final_report = run_final_pick_pipeline(
        predictions_csv=predictions_csv,
        output_dir=output_dir,
        calibration_history_csv=calibration_history_csv,
        line_movement_history_csv=line_movement_history_csv,
        market_profile_history_csv=market_profile_history_csv,
        bankroll_policy=bankroll_policy,
    )
    run_id = create_run(
        db_path,
        run_type="daily_agent",
        run_mode=run_mode,
        model_version=model_version,
        pipeline_version=pipeline_version,
        output_dir=str(output_dir),
        notes="manual daily run" if run_mode == "manual" else "automated daily run",
    )
    scored_rows = _read_csv_rows(final_report.outputs.all_scored_csv)
    stored = record_pick_rows(db_path, run_id, scored_rows, model_version=model_version, pipeline_version=pipeline_version)
    store_summary = summarize_store(db_path)
    report_path = output_dir / "daily_runner_report.json"
    report = DailyRunnerReport(
        run_id=run_id,
        run_mode=run_mode,
        automated_daily_enabled=automated_daily_enabled,
        predictions_csv=str(predictions_csv),
        output_dir=str(output_dir),
        db_path=str(db_path),
        final_bets=final_report.final_bets,
        watchlist=final_report.watchlist,
        rejected=final_report.rejected,
        stored_rows=stored,
        store_pick_count=store_summary.pick_count,
        report_json=str(report_path),
        warnings=final_report.warnings,
        notes=[
            "This runner executes once by default; it does not schedule itself.",
            "Automated daily mode is disabled unless run_mode='automated_daily' and automated_daily_enabled=True are both set.",
        ],
    )
    report_path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

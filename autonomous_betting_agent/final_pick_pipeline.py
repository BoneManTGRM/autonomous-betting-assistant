from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .accuracy_calibration import apply_calibration
from .bankroll_exposure import BankrollPolicy, apply_bankroll_exposure, summarize_bankroll
from .ensemble_agreement import apply_ensemble_scoring, summarize_ensemble
from .line_movement_model import enrich_line_movement_rows, summarize_line_movement
from .market_accuracy_profiles import enrich_with_market_profiles, summarize_profiles
from .multi_source_fusion import FusionPolicy, fuse_rows
from .prediction_validator import ValidationPolicy, validate_prediction_rows, write_report as write_validation_report
from .reporting import build_daily_markdown_report


@dataclass(frozen=True)
class FinalPickOutputs:
    all_scored_csv: str
    final_bets_csv: str
    watchlist_csv: str
    rejected_picks_csv: str
    validation_report_json: str | None
    daily_report_json: str
    daily_summary_md: str


@dataclass(frozen=True)
class FinalPickReport:
    raw_rows: int
    final_bets: int
    watchlist: int
    rejected: int
    total_stake_units: float
    validation_status: str | None
    steps_run: list[str]
    outputs: FinalPickOutputs
    warnings: list[str]
    notes: list[str]


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _split_rows(rows: list[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    final_bets = [row for row in rows if row.get("bankroll_action") == "BET"]
    watchlist = [row for row in rows if row.get("bankroll_action") == "WATCH"]
    rejected = [row for row in rows if row.get("bankroll_action") == "REJECT"]
    return final_bets, watchlist, rejected


def run_final_pick_pipeline(
    *,
    predictions_csv: str | Path,
    output_dir: str | Path = "data/final_pick_pipeline",
    calibration_history_csv: str | Path | None = None,
    line_movement_history_csv: str | Path | None = None,
    market_profile_history_csv: str | Path | None = None,
    bankroll_policy: BankrollPolicy = BankrollPolicy(),
    validation_policy: ValidationPolicy | None = ValidationPolicy(),
    fusion_policy: FusionPolicy | None = FusionPolicy(),
    strict_validation: bool = False,
) -> FinalPickReport:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    steps: list[str] = []
    warnings: list[str] = []
    validation_status: str | None = None
    validation_report_json: Path | None = None

    rows: list[Mapping[str, Any]] = read_csv_rows(predictions_csv)
    raw_count = len(rows)

    if validation_policy is not None:
        validated, validation_report = validate_prediction_rows(list(rows), policy=validation_policy)
        rows = validated
        validation_status = validation_report.status
        validation_report_json = base / "prediction_validation_report.json"
        write_validation_report(validation_report, validation_report_json)
        steps.append("prediction_validation")
        if validation_report.status == "FAIL":
            warnings.append(f"prediction validation failed with {validation_report.error_count} error(s)")
            if strict_validation:
                rows = [row for row in rows if row.get("validation_status") == "VALID"]
        elif validation_report.status == "WATCH":
            warnings.append(f"prediction validation passed with {validation_report.warning_count} warning(s)")

    if fusion_policy is not None:
        rows = fuse_rows(list(rows), policy=fusion_policy, override_model_probability=True)
        steps.append("multi_source_fusion")
        if any(not row.get("market_probability") for row in rows):
            warnings.append("some rows are missing market probability; fusion used model probability fallback where available")

    if calibration_history_csv:
        history = read_csv_rows(calibration_history_csv)
        calibrated, calibration_report = apply_calibration(list(rows), history)
        rows = calibrated
        steps.append("accuracy_calibration")
        if calibration_report.calibrated_rows < raw_count:
            warnings.append("some rows could not be calibrated because probability was missing")
    else:
        warnings.append("calibration history not supplied; using raw/fused probabilities")

    if line_movement_history_csv:
        history = read_csv_rows(line_movement_history_csv)
        rows = enrich_line_movement_rows(list(rows), history)
        steps.append("line_movement_learning")
        movement_report = summarize_line_movement(list(rows), history)
        if movement_report.with_closing_rows < raw_count:
            warnings.append("some rows are missing closing odds for line-movement scoring")
    else:
        warnings.append("line movement history not supplied; market support may be weaker")

    if market_profile_history_csv:
        history = read_csv_rows(market_profile_history_csv)
        rows = enrich_with_market_profiles(list(rows), history)
        steps.append("market_accuracy_profiles")
        profile_report = summarize_profiles(list(rows), history)
        if profile_report.profile_count == 0:
            warnings.append("no market accuracy profiles met sample-size requirements")
    else:
        warnings.append("market profile history not supplied; trust levels default lower")

    rows = apply_ensemble_scoring(list(rows))
    steps.append("ensemble_agreement")
    ensemble_report = summarize_ensemble(list(rows))
    if ensemble_report.accept_rows == 0:
        warnings.append("ensemble produced zero ACCEPT rows")

    rows = apply_bankroll_exposure(list(rows), policy=bankroll_policy)
    steps.append("bankroll_exposure")
    bankroll_report = summarize_bankroll(list(rows))

    final_bets, watchlist, rejected = _split_rows(list(rows))
    all_scored = base / "all_scored_picks.csv"
    final_bets_csv = base / "final_bets.csv"
    watchlist_csv = base / "watchlist.csv"
    rejected_csv = base / "rejected_picks.csv"
    report_json = base / "daily_report.json"
    summary_md = base / "daily_summary.md"
    write_csv_rows(rows, all_scored)
    write_csv_rows(final_bets, final_bets_csv)
    write_csv_rows(watchlist, watchlist_csv)
    write_csv_rows(rejected, rejected_csv)
    build_daily_markdown_report(
        final_bets_csv=final_bets_csv,
        watchlist_csv=watchlist_csv,
        rejected_picks_csv=rejected_csv,
        output_md=summary_md,
        warnings=warnings,
    )

    report = FinalPickReport(
        raw_rows=raw_count,
        final_bets=len(final_bets),
        watchlist=len(watchlist),
        rejected=len(rejected),
        total_stake_units=bankroll_report.total_stake_units,
        validation_status=validation_status,
        steps_run=steps,
        outputs=FinalPickOutputs(
            all_scored_csv=str(all_scored),
            final_bets_csv=str(final_bets_csv),
            watchlist_csv=str(watchlist_csv),
            rejected_picks_csv=str(rejected_csv),
            validation_report_json=str(validation_report_json) if validation_report_json else None,
            daily_report_json=str(report_json),
            daily_summary_md=str(summary_md),
        ),
        warnings=warnings,
        notes=[
            "Final bets are rows that survived validation, multi-source fusion, calibration/profile/ensemble scoring and bankroll exposure checks.",
            "Fusion starts from market probability and only lets stats, context, injuries and ARA memory move the line within capped limits.",
            "Watchlist rows are not automatic bets; they need better odds, more data or lower exposure risk.",
            "Rejected rows should not be used for performance claims unless separately tracked as rejected candidates.",
        ],
    )
    report_json.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

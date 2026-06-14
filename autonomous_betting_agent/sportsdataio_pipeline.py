from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .accuracy_calibration import apply_calibration, read_csv_rows as read_calibration_csv_rows, write_csv_rows as write_calibration_csv_rows, write_report as write_calibration_report
from .odds_clv import enrich_predictions_with_odds, read_csv_rows as read_odds_csv_rows, summarize_odds_enrichment, write_report as write_odds_report
from .player_prop_features import enrich_props_with_player_features, read_csv_rows as read_feature_csv_rows, write_csv_rows
from .player_props import apply_player_prop_layer, rank_player_props
from .profit_goal import ProfitGoalPolicy, review_profit_goal_rows, write_report as write_profit_goal_report
from .sportsdataio import SportsDataIOClient, payload_to_records, write_csv_records, write_json_payload
from .sportsdataio_normalize import write_normalized_csv
from .sportsdataio_player_features import build_player_features, write_player_features
from .sportsdataio_quality import PipelineQualityGate, evaluate_pipeline_quality
from .sportsdataio_results import enrich_predictions_with_results, read_csv_rows as read_result_csv_rows, write_csv_rows as write_result_csv_rows


@dataclass(frozen=True)
class PipelineOutputs:
    raw_games_json: str | None = None
    flat_games_csv: str | None = None
    canonical_games_csv: str | None = None
    predictions_calibrated_csv: str | None = None
    accuracy_calibration_report_json: str | None = None
    predictions_with_results_csv: str | None = None
    odds_clv_report_json: str | None = None
    profit_goal_report_json: str | None = None
    raw_player_stats_json: str | None = None
    flat_player_stats_csv: str | None = None
    player_features_csv: str | None = None
    player_props_enriched_csv: str | None = None
    player_props_checked_csv: str | None = None
    player_props_ranked_csv: str | None = None
    report_json: str | None = None


@dataclass(frozen=True)
class PipelineReport:
    steps_run: list[str]
    warnings: list[str]
    counts: dict[str, int]
    outputs: PipelineOutputs
    quality_gate: PipelineQualityGate | None = None


def _path(base_dir: Path, name: str) -> Path:
    return base_dir / name


def _write_report(report: PipelineReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _score_player_props(enriched_props_csv: Path, checked_output: Path, ranked_output: Path, *, include_watch: bool) -> tuple[int, int]:
    props = pd.read_csv(enriched_props_csv)
    checked = apply_player_prop_layer(props)
    ranked = rank_player_props(props, include_watch=include_watch)
    checked_output.parent.mkdir(parents=True, exist_ok=True)
    ranked_output.parent.mkdir(parents=True, exist_ok=True)
    checked.to_csv(checked_output, index=False)
    ranked.to_csv(ranked_output, index=False)
    return len(checked), len(ranked)


def _add_goal_counts(counts: dict[str, int], goal_status: str, checks: dict[str, bool | None]) -> None:
    counts[f"profit_goal_status_{goal_status.lower()}"] = 1
    for key, value in checks.items():
        suffix = "unknown" if value is None else str(value).lower()
        counts[f"profit_goal_check_{key}_{suffix}"] = 1


def run_sportsdataio_pipeline(
    *,
    client: SportsDataIOClient | None = None,
    sport: str = "nfl",
    games_endpoint: str | None = None,
    player_stats_endpoint: str | None = None,
    predictions_csv: str | Path | None = None,
    player_props_csv: str | Path | None = None,
    odds_csv: str | Path | None = None,
    calibration_history_csv: str | Path | None = None,
    existing_canonical_games_csv: str | Path | None = None,
    existing_player_features_csv: str | Path | None = None,
    output_dir: str | Path = "data/sportsdataio_pipeline",
    include_watch: bool = False,
    run_profit_goal_review: bool = True,
    profit_goal_min_finished: int = 200,
    allow_missing_clv: bool = False,
) -> PipelineReport:
    """Run the SportsDataIO ingestion/enrichment pipeline.

    The function is intentionally modular: if an endpoint is omitted, that step is
    skipped. Existing canonical games or player feature CSVs can be supplied when
    the caller wants to avoid an API request during testing or replay.
    """
    base_dir = Path(output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    steps: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    raw_games_json: Path | None = None
    flat_games_csv: Path | None = None
    canonical_games_csv: Path | None = Path(existing_canonical_games_csv) if existing_canonical_games_csv else None
    predictions_calibrated_csv: Path | None = None
    accuracy_calibration_report_json: Path | None = None
    predictions_with_results_csv: Path | None = None
    odds_clv_report_json: Path | None = None
    profit_goal_report_json: Path | None = None
    raw_player_stats_json: Path | None = None
    flat_player_stats_csv: Path | None = None
    player_features_csv: Path | None = Path(existing_player_features_csv) if existing_player_features_csv else None
    player_props_enriched_csv: Path | None = None
    player_props_checked_csv: Path | None = None
    player_props_ranked_csv: Path | None = None

    if games_endpoint:
        if client is None:
            raise ValueError("client is required when games_endpoint is provided")
        payload = client.raw_endpoint(games_endpoint, sport=sport, subfeed="scores")
        game_records = payload_to_records(payload)
        raw_games_json = _path(base_dir, "sportsdataio_games_raw.json")
        flat_games_csv = _path(base_dir, "sportsdataio_games_flat.csv")
        canonical_games_csv = _path(base_dir, "sportsdataio_games_canonical.csv")
        write_json_payload(payload, raw_games_json)
        write_csv_records(game_records, flat_games_csv)
        normalized_games = write_normalized_csv(game_records, canonical_games_csv, dataset_type="games", sport=sport)
        steps.append("fetch_games")
        counts["games_raw_records"] = len(game_records)
        counts["games_canonical_records"] = len(normalized_games)
    elif canonical_games_csv:
        steps.append("use_existing_canonical_games")

    if predictions_csv:
        if canonical_games_csv is None:
            warnings.append("predictions_csv supplied but no games endpoint or canonical games CSV was provided")
        else:
            predictions = read_result_csv_rows(predictions_csv)
            counts["prediction_rows"] = len(predictions)
            if calibration_history_csv:
                history_rows = read_calibration_csv_rows(calibration_history_csv)
                predictions, calibration_report = apply_calibration(predictions, history_rows)
                predictions_calibrated_csv = _path(base_dir, "predictions_calibrated.csv")
                accuracy_calibration_report_json = _path(base_dir, "accuracy_calibration_report.json")
                write_calibration_csv_rows(predictions, predictions_calibrated_csv)
                write_calibration_report(calibration_report, accuracy_calibration_report_json)
                steps.append("apply_accuracy_calibration")
                counts["calibration_history_rows"] = len(history_rows)
                counts["calibrated_prediction_rows"] = calibration_report.calibrated_rows
                if calibration_report.calibrated_rows < len(predictions):
                    warnings.append("calibration: some prediction rows were missing model probability")

            games = read_result_csv_rows(canonical_games_csv)
            enriched_predictions = enrich_predictions_with_results(predictions, games)
            steps.append("apply_game_results")
            for row in enriched_predictions:
                key = f"prediction_match_{row.get('sdio_result_match_status', 'unknown')}"
                counts[key] = counts.get(key, 0) + 1

            if odds_csv:
                odds_rows = read_odds_csv_rows(odds_csv)
                enriched_predictions = enrich_predictions_with_odds(enriched_predictions, odds_rows, source="odds_csv")
                odds_report = summarize_odds_enrichment(enriched_predictions)
                odds_clv_report_json = _path(base_dir, "odds_clv_report.json")
                write_odds_report(odds_report, odds_clv_report_json)
                steps.append("apply_odds_clv")
                counts["odds_rows"] = len(odds_rows)
                counts["odds_matched_rows"] = odds_report.matched_rows
                counts["odds_unmatched_rows"] = odds_report.unmatched_rows
                counts["odds_missing_entry_rows"] = odds_report.missing_entry_rows
                counts["odds_missing_closing_rows"] = odds_report.missing_closing_rows
                if odds_report.unmatched_rows:
                    warnings.append("odds_clv: some prediction rows were not matched to odds data")
                if odds_report.missing_closing_rows and not allow_missing_clv:
                    warnings.append("odds_clv: some prediction rows are missing closing odds")

            predictions_with_results_csv = _path(base_dir, "predictions_with_sportsdataio_results.csv")
            write_result_csv_rows(enriched_predictions, predictions_with_results_csv)

            if run_profit_goal_review:
                profit_goal_policy = ProfitGoalPolicy(
                    min_finished=profit_goal_min_finished,
                    require_positive_clv=not allow_missing_clv,
                )
                profit_report = review_profit_goal_rows(enriched_predictions, policy=profit_goal_policy)
                profit_goal_report_json = _path(base_dir, "profit_goal_report.json")
                write_profit_goal_report(profit_report, profit_goal_report_json)
                steps.append("review_profit_goal")
                counts["profit_goal_finished_rows"] = profit_report.finished_rows
                counts["profit_goal_wins"] = profit_report.wins
                counts["profit_goal_losses"] = profit_report.losses
                counts["profit_goal_pushes"] = profit_report.pushes
                _add_goal_counts(counts, profit_report.status, profit_report.goal_checks)
                if profit_report.status != "GOAL_MET":
                    warnings.extend(f"profit_goal: {item}" for item in profit_report.required_actions)

    if player_stats_endpoint:
        if client is None:
            raise ValueError("client is required when player_stats_endpoint is provided")
        payload = client.raw_endpoint(player_stats_endpoint, sport=sport, subfeed="stats")
        stat_records = payload_to_records(payload)
        raw_player_stats_json = _path(base_dir, "sportsdataio_player_stats_raw.json")
        flat_player_stats_csv = _path(base_dir, "sportsdataio_player_stats_flat.csv")
        player_features_csv = _path(base_dir, "sportsdataio_player_features.csv")
        write_json_payload(payload, raw_player_stats_json)
        write_csv_records(stat_records, flat_player_stats_csv)
        player_features = build_player_features(stat_records, sport=sport)
        write_player_features(player_features, player_features_csv)
        steps.append("build_player_features")
        counts["player_stat_records"] = len(stat_records)
        counts["player_feature_records"] = len(player_features)
        counts["player_feature_ready"] = sum(1 for row in player_features if row.get("feature_ready") == "true")
    elif player_features_csv:
        steps.append("use_existing_player_features")

    if player_props_csv:
        if player_features_csv is None:
            warnings.append("player_props_csv supplied but no player stats endpoint or player feature CSV was provided")
        else:
            props = read_feature_csv_rows(player_props_csv)
            features = read_feature_csv_rows(player_features_csv)
            enriched_props = enrich_props_with_player_features(props, features)
            player_props_enriched_csv = _path(base_dir, "player_props_enriched_with_features.csv")
            player_props_checked_csv = _path(base_dir, "player_props_checked.csv")
            player_props_ranked_csv = _path(base_dir, "player_props_ranked.csv")
            write_csv_rows(enriched_props, player_props_enriched_csv)
            checked_count, ranked_count = _score_player_props(player_props_enriched_csv, player_props_checked_csv, player_props_ranked_csv, include_watch=include_watch)
            steps.append("enrich_and_score_player_props")
            counts["player_prop_rows"] = len(props)
            counts["player_prop_checked_rows"] = checked_count
            counts["player_prop_ranked_rows"] = ranked_count
            for row in enriched_props:
                key = f"player_feature_match_{row.get('feature_match_status', 'unknown')}"
                counts[key] = counts.get(key, 0) + 1

    quality_gate = evaluate_pipeline_quality(steps_run=steps, warnings=warnings, counts=counts)
    report_json = _path(base_dir, "sportsdataio_pipeline_report.json")
    report = PipelineReport(
        steps_run=steps,
        warnings=warnings,
        counts=counts,
        outputs=PipelineOutputs(
            raw_games_json=str(raw_games_json) if raw_games_json else None,
            flat_games_csv=str(flat_games_csv) if flat_games_csv else None,
            canonical_games_csv=str(canonical_games_csv) if canonical_games_csv else None,
            predictions_calibrated_csv=str(predictions_calibrated_csv) if predictions_calibrated_csv else None,
            accuracy_calibration_report_json=str(accuracy_calibration_report_json) if accuracy_calibration_report_json else None,
            predictions_with_results_csv=str(predictions_with_results_csv) if predictions_with_results_csv else None,
            odds_clv_report_json=str(odds_clv_report_json) if odds_clv_report_json else None,
            profit_goal_report_json=str(profit_goal_report_json) if profit_goal_report_json else None,
            raw_player_stats_json=str(raw_player_stats_json) if raw_player_stats_json else None,
            flat_player_stats_csv=str(flat_player_stats_csv) if flat_player_stats_csv else None,
            player_features_csv=str(player_features_csv) if player_features_csv else None,
            player_props_enriched_csv=str(player_props_enriched_csv) if player_props_enriched_csv else None,
            player_props_checked_csv=str(player_props_checked_csv) if player_props_checked_csv else None,
            player_props_ranked_csv=str(player_props_ranked_csv) if player_props_ranked_csv else None,
            report_json=str(report_json),
        ),
        quality_gate=quality_gate,
    )
    _write_report(report, report_json)
    return report

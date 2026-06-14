from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .api_clients import OddsAPIClient, WeatherAPIClient
from .final_pick_pipeline import run_final_pick_pipeline
from .odds_api import odds_api_payload_to_rows, write_json_payload as write_odds_json, write_odds_rows
from .odds_clv import enrich_predictions_with_odds
from .sportsdataio import SportsDataIOClient, payload_to_records, write_csv_records, write_json_payload
from .sportsdataio_normalize import write_normalized_csv
from .sportsdataio_results import enrich_predictions_with_results


@dataclass(frozen=True)
class PredictorAPIOutputs:
    api_enriched_predictions_csv: str
    raw_sportsdataio_games_json: str | None = None
    canonical_games_csv: str | None = None
    raw_odds_json: str | None = None
    odds_csv: str | None = None
    raw_weather_json: str | None = None
    final_report_json: str | None = None
    final_bets_csv: str | None = None
    watchlist_csv: str | None = None
    rejected_picks_csv: str | None = None


@dataclass(frozen=True)
class PredictorAPIReport:
    steps_run: list[str]
    warnings: list[str]
    counts: dict[str, int]
    outputs: PredictorAPIOutputs


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


def _mark_weather(rows: list[Mapping[str, Any]], *, location: str, available: bool) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["weather_api_status"] = "available" if available else "not_available"
        item["weather_location"] = item.get("weather_location") or location
        output.append(item)
    return output


def run_predictor_api_pipeline(
    *,
    predictions_csv: str | Path,
    output_dir: str | Path = "data/predictor_api_pipeline",
    sportsdataio_client: SportsDataIOClient | None = None,
    sportsdataio_sport: str = "nfl",
    sportsdataio_games_endpoint: str | None = None,
    odds_client: OddsAPIClient | None = None,
    odds_sport_key: str | None = None,
    odds_regions: str = "us",
    odds_markets: str = "h2h,spreads,totals",
    weather_client: WeatherAPIClient | None = None,
    weather_location: str | None = None,
    calibration_history_csv: str | Path | None = None,
    line_movement_history_csv: str | Path | None = None,
    market_profile_history_csv: str | Path | None = None,
    run_final_pipeline: bool = True,
) -> PredictorAPIReport:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    steps: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    predictions = read_csv_rows(predictions_csv)
    counts["prediction_rows"] = len(predictions)
    enriched: list[Mapping[str, Any]] = predictions

    raw_sdio_json: Path | None = None
    canonical_games_csv: Path | None = None
    if sportsdataio_client and sportsdataio_games_endpoint:
        payload = sportsdataio_client.raw_endpoint(sportsdataio_games_endpoint, sport=sportsdataio_sport, subfeed="scores")
        records = payload_to_records(payload)
        raw_sdio_json = base / "sportsdataio_games_raw.json"
        flat_sdio_csv = base / "sportsdataio_games_flat.csv"
        canonical_games_csv = base / "sportsdataio_games_canonical.csv"
        write_json_payload(payload, raw_sdio_json)
        write_csv_records(records, flat_sdio_csv)
        canonical = write_normalized_csv(records, canonical_games_csv, dataset_type="games", sport=sportsdataio_sport)
        enriched = enrich_predictions_with_results(list(enriched), read_csv_rows(canonical_games_csv))
        steps.append("sportsdataio_games_results")
        counts["sportsdataio_game_records"] = len(records)
        counts["canonical_game_records"] = len(canonical)
    else:
        warnings.append("SportsDataIO games endpoint/client not supplied; skipping game result enrichment")

    raw_odds_json: Path | None = None
    odds_csv: Path | None = None
    if odds_client and odds_sport_key:
        payload = odds_client.odds(sport_key=odds_sport_key, regions=odds_regions, markets=odds_markets)
        odds_rows = odds_api_payload_to_rows(payload)
        raw_odds_json = base / "odds_api_raw.json"
        odds_csv = base / "odds_api_flat.csv"
        write_odds_json(payload, raw_odds_json)
        write_odds_rows(odds_rows, odds_csv)
        enriched = enrich_predictions_with_odds(list(enriched), odds_rows, source="odds_api")
        steps.append("odds_api_clv")
        counts["odds_api_rows"] = len(odds_rows)
    else:
        warnings.append("Odds API client/sport key not supplied; skipping odds enrichment")

    raw_weather_json: Path | None = None
    if weather_client and weather_location:
        payload = weather_client.forecast(location=weather_location, days=1)
        raw_weather_json = base / "weatherapi_raw.json"
        raw_weather_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        enriched = _mark_weather(list(enriched), location=weather_location, available=True)
        steps.append("weatherapi_fetch")
        counts["weatherapi_locations"] = 1
    else:
        enriched = _mark_weather(list(enriched), location=weather_location or "", available=False)
        warnings.append("WeatherAPI client/location not supplied; marking weather as unavailable")

    enriched_csv = base / "predictor_api_enriched.csv"
    write_csv_rows(enriched, enriched_csv)

    final_report_json = final_bets_csv = watchlist_csv = rejected_picks_csv = None
    if run_final_pipeline:
        final_report = run_final_pick_pipeline(
            predictions_csv=enriched_csv,
            output_dir=base / "final_pick_pipeline",
            calibration_history_csv=calibration_history_csv,
            line_movement_history_csv=line_movement_history_csv,
            market_profile_history_csv=market_profile_history_csv,
        )
        steps.append("final_pick_pipeline")
        final_report_json = final_report.outputs.daily_report_json
        final_bets_csv = final_report.outputs.final_bets_csv
        watchlist_csv = final_report.outputs.watchlist_csv
        rejected_picks_csv = final_report.outputs.rejected_picks_csv
        warnings.extend(final_report.warnings)
        counts["final_bets"] = final_report.final_bets
        counts["watchlist"] = final_report.watchlist
        counts["rejected"] = final_report.rejected

    report = PredictorAPIReport(
        steps_run=steps,
        warnings=warnings,
        counts=counts,
        outputs=PredictorAPIOutputs(
            api_enriched_predictions_csv=str(enriched_csv),
            raw_sportsdataio_games_json=str(raw_sdio_json) if raw_sdio_json else None,
            canonical_games_csv=str(canonical_games_csv) if canonical_games_csv else None,
            raw_odds_json=str(raw_odds_json) if raw_odds_json else None,
            odds_csv=str(odds_csv) if odds_csv else None,
            raw_weather_json=str(raw_weather_json) if raw_weather_json else None,
            final_report_json=final_report_json,
            final_bets_csv=final_bets_csv,
            watchlist_csv=watchlist_csv,
            rejected_picks_csv=rejected_picks_csv,
        ),
    )
    (base / "predictor_api_report.json").write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

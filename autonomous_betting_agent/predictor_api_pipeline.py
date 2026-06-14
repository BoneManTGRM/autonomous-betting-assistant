from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .api_budget import APIBudgetManager
from .api_clients import OddsAPIClient, WeatherAPIClient
from .environment_intelligence import enrich_rows_with_environment
from .final_pick_pipeline import run_final_pick_pipeline
from .odds_api import odds_api_payload_to_rows, write_json_payload as write_odds_json, write_odds_rows
from .odds_clv import enrich_predictions_with_odds
from .sport_key_resolver import resolve_sport_key
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
    api_call_report_json: str | None = None
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


def _weather_row(payload: Mapping[str, Any], location: str) -> dict[str, Any]:
    current = payload.get("current") if isinstance(payload.get("current"), Mapping) else {}
    return {
        "weather_location": location,
        "temp_c": current.get("temp_c", ""),
        "temp_f": current.get("temp_f", ""),
        "wind_kph": current.get("wind_kph", ""),
        "wind_mph": current.get("wind_mph", ""),
        "gust_mph": current.get("gust_mph", ""),
        "precip_mm": current.get("precip_mm", ""),
        "humidity": current.get("humidity", ""),
    }


def _apply_weather_payload(rows: list[Mapping[str, Any]], payload: Mapping[str, Any], *, location: str, sport: str) -> list[dict[str, Any]]:
    weather = _weather_row(payload, location)
    output: list[dict[str, Any]] = []
    for row in rows:
        merged = dict(row)
        merged.update(weather)
        merged["weather_api_status"] = "available"
        output.append(merged)
    return enrich_rows_with_environment(output, sport=sport)


def _budgeted_call(budget: APIBudgetManager | None, *, provider: str, endpoint: str, params: Mapping[str, Any], fetcher):
    if budget is None:
        return fetcher()
    return budget.call(provider=provider, endpoint=endpoint, params=params, fetcher=fetcher)


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
    sport_search: str | None = None,
    game_search: str | None = None,
    calibration_history_csv: str | Path | None = None,
    line_movement_history_csv: str | Path | None = None,
    market_profile_history_csv: str | Path | None = None,
    run_final_pipeline: bool = True,
    budget_manager: APIBudgetManager | None = None,
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
        payload = _budgeted_call(
            budget_manager,
            provider="sportsdataio",
            endpoint=sportsdataio_games_endpoint,
            params={"sport": sportsdataio_sport, "subfeed": "scores"},
            fetcher=lambda: sportsdataio_client.raw_endpoint(sportsdataio_games_endpoint, sport=sportsdataio_sport, subfeed="scores"),
        )
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
    resolved_sport_key = odds_sport_key
    if odds_client and not resolved_sport_key and sport_search:
        sports_payload = _budgeted_call(
            budget_manager,
            provider="odds_api",
            endpoint="sports",
            params={"all": "false"},
            fetcher=lambda: odds_client.sports(),
        )
        match = resolve_sport_key(sports_payload if isinstance(sports_payload, list) else [], sport_search=sport_search, game=game_search or "")
        resolved_sport_key = match.matched_sport_key
        counts["sport_key_match_confidence_pct"] = int(round(match.match_confidence * 100))
        steps.append("resolve_odds_sport_key")
        if not resolved_sport_key:
            warnings.append("could not resolve Odds API sport key from sport_search")

    if odds_client and resolved_sport_key:
        payload = _budgeted_call(
            budget_manager,
            provider="odds_api",
            endpoint=f"sports/{resolved_sport_key}/odds",
            params={"regions": odds_regions, "markets": odds_markets},
            fetcher=lambda: odds_client.odds(sport_key=resolved_sport_key or "", regions=odds_regions, markets=odds_markets),
        )
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
        payload = _budgeted_call(
            budget_manager,
            provider="weatherapi",
            endpoint="forecast.json",
            params={"q": weather_location, "days": 1},
            fetcher=lambda: weather_client.forecast(location=weather_location, days=1),
        )
        raw_weather_json = base / "weatherapi_raw.json"
        raw_weather_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        enriched = _apply_weather_payload(list(enriched), payload if isinstance(payload, Mapping) else {}, location=weather_location, sport=sportsdataio_sport)
        steps.append("weatherapi_intelligence")
        counts["weatherapi_locations"] = 1
    else:
        enriched = enrich_rows_with_environment([dict(row, weather_api_status="not_available", weather_location=weather_location or "") for row in enriched], sport=sportsdataio_sport)
        warnings.append("WeatherAPI client/location not supplied; weather scoring uses only existing row fields")

    api_call_report_json: Path | None = None
    if budget_manager is not None:
        api_call_report_json = base / "api_call_report.json"
        budget_manager.write_report(api_call_report_json)
        counts["api_calls_made"] = budget_manager.calls_made
        counts["api_cache_hits"] = budget_manager.cache_hits
        steps.append("api_budget_report")

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
            api_call_report_json=str(api_call_report_json) if api_call_report_json else None,
            final_report_json=final_report_json,
            final_bets_csv=final_bets_csv,
            watchlist_csv=watchlist_csv,
            rejected_picks_csv=rejected_picks_csv,
        ),
    )
    (base / "predictor_api_report.json").write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

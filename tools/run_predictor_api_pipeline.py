from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.api_clients import OddsAPIClient, OddsAPIConfig, WeatherAPIClient, WeatherAPIConfig
from autonomous_betting_agent.predictor_api_pipeline import run_predictor_api_pipeline
from autonomous_betting_agent.sportsdataio import SportsDataIOClient, SportsDataIOConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Predictor Pro with SportsDataIO, WeatherAPI and Odds API inputs.")
    parser.add_argument("predictions_csv", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/predictor_api_pipeline"))
    parser.add_argument("--sportsdataio-sport", default="nfl")
    parser.add_argument("--sportsdataio-games-endpoint", default=None)
    parser.add_argument("--sportsdataio-api-key", default=None)
    parser.add_argument("--sportsdataio-auth-mode", choices=["header", "query"], default="header")
    parser.add_argument("--odds-sport-key", default=None)
    parser.add_argument("--odds-regions", default="us")
    parser.add_argument("--odds-markets", default="h2h,spreads,totals")
    parser.add_argument("--odds-api-key", default=None)
    parser.add_argument("--weather-location", default=None)
    parser.add_argument("--weatherapi-key", default=None)
    parser.add_argument("--calibration-history-csv", type=Path, default=None)
    parser.add_argument("--line-movement-history-csv", type=Path, default=None)
    parser.add_argument("--market-profile-history-csv", type=Path, default=None)
    parser.add_argument("--skip-final-pipeline", action="store_true")
    args = parser.parse_args()

    sdio_client = None
    if args.sportsdataio_games_endpoint:
        sdio_config = SportsDataIOConfig(
            api_key=args.sportsdataio_api_key,
            sport=args.sportsdataio_sport,
            auth_mode=args.sportsdataio_auth_mode,
        ) if args.sportsdataio_api_key else SportsDataIOConfig.from_env(sport=args.sportsdataio_sport, auth_mode=args.sportsdataio_auth_mode)
        sdio_client = SportsDataIOClient(sdio_config)

    odds_client = None
    if args.odds_sport_key:
        odds_config = OddsAPIConfig(api_key=args.odds_api_key) if args.odds_api_key else OddsAPIConfig.from_env()
        odds_client = OddsAPIClient(odds_config)

    weather_client = None
    if args.weather_location:
        weather_config = WeatherAPIConfig(api_key=args.weatherapi_key) if args.weatherapi_key else WeatherAPIConfig.from_env()
        weather_client = WeatherAPIClient(weather_config)

    report = run_predictor_api_pipeline(
        predictions_csv=args.predictions_csv,
        output_dir=args.output_dir,
        sportsdataio_client=sdio_client,
        sportsdataio_sport=args.sportsdataio_sport,
        sportsdataio_games_endpoint=args.sportsdataio_games_endpoint,
        odds_client=odds_client,
        odds_sport_key=args.odds_sport_key,
        odds_regions=args.odds_regions,
        odds_markets=args.odds_markets,
        weather_client=weather_client,
        weather_location=args.weather_location,
        calibration_history_csv=args.calibration_history_csv,
        line_movement_history_csv=args.line_movement_history_csv,
        market_profile_history_csv=args.market_profile_history_csv,
        run_final_pipeline=not args.skip_final_pipeline,
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

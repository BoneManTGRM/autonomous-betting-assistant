from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote

import requests


class ExternalAPIError(RuntimeError):
    """Raised when an external API cannot be called or returns bad data."""


@dataclass(frozen=True)
class OddsAPIConfig:
    api_key: str
    base_url: str = "https://api.the-odds-api.com/v4"
    timeout_seconds: float = 30.0
    env_var: str = "ODDS_API_KEY"

    @classmethod
    def from_env(cls, *, env_var: str = "ODDS_API_KEY", base_url: str = "https://api.the-odds-api.com/v4", timeout_seconds: float = 30.0) -> "OddsAPIConfig":
        api_key = os.environ.get(env_var, "").strip()
        if not api_key:
            raise ExternalAPIError(f"Missing Odds API key. Set {env_var} or pass an explicit key.")
        return cls(api_key=api_key, base_url=base_url, timeout_seconds=timeout_seconds, env_var=env_var)


class OddsAPIClient:
    def __init__(self, config: OddsAPIConfig, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()

    def get(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        query = dict(params or {})
        query["apiKey"] = self.config.api_key
        url = f"{self.config.base_url.rstrip('/')}/{path.strip('/')}"
        response = self.session.get(url, params=query, timeout=self.config.timeout_seconds)
        if response.status_code >= 400:
            raise ExternalAPIError(f"Odds API request failed with HTTP {response.status_code}: {response.text[:500]}")
        try:
            return response.json()
        except ValueError as exc:
            raise ExternalAPIError("Odds API response was not valid JSON.") from exc

    def odds(
        self,
        *,
        sport_key: str,
        regions: str = "us",
        markets: str = "h2h,spreads,totals",
        odds_format: str = "decimal",
        date_format: str = "iso",
        bookmakers: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": date_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers
        return self.get(f"sports/{quote(sport_key, safe='')}/odds", params=params)


@dataclass(frozen=True)
class WeatherAPIConfig:
    api_key: str
    base_url: str = "https://api.weatherapi.com/v1"
    timeout_seconds: float = 30.0
    env_var: str = "WEATHERAPI_KEY"

    @classmethod
    def from_env(cls, *, env_var: str = "WEATHERAPI_KEY", base_url: str = "https://api.weatherapi.com/v1", timeout_seconds: float = 30.0) -> "WeatherAPIConfig":
        api_key = os.environ.get(env_var, "").strip()
        if not api_key:
            raise ExternalAPIError(f"Missing WeatherAPI key. Set {env_var} or pass an explicit key.")
        return cls(api_key=api_key, base_url=base_url, timeout_seconds=timeout_seconds, env_var=env_var)


class WeatherAPIClient:
    def __init__(self, config: WeatherAPIConfig, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()

    def get(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        query = dict(params or {})
        query["key"] = self.config.api_key
        url = f"{self.config.base_url.rstrip('/')}/{path.strip('/')}"
        response = self.session.get(url, params=query, timeout=self.config.timeout_seconds)
        if response.status_code >= 400:
            raise ExternalAPIError(f"WeatherAPI request failed with HTTP {response.status_code}: {response.text[:500]}")
        try:
            return response.json()
        except ValueError as exc:
            raise ExternalAPIError("WeatherAPI response was not valid JSON.") from exc

    def forecast(self, *, location: str, days: int = 1, aqi: str = "no", alerts: str = "yes") -> Any:
        return self.get("forecast.json", params={"q": location, "days": days, "aqi": aqi, "alerts": alerts})

    def current(self, *, location: str, aqi: str = "no") -> Any:
        return self.get("current.json", params={"q": location, "aqi": aqi})

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping

import requests

WEATHERAPI_HOST = "https://api.weatherapi.com/v1"
MAX_FORECAST_DAYS = 14
PLACEHOLDER_KEYS = {
    "your_weatherapi_key_here",
    "weatherapi_key",
    "your_key_here",
    "paste_key_here",
    "replace_me",
}


@dataclass(frozen=True)
class WeatherSnapshot:
    location_query: str
    location_name: str
    region: str
    country: str
    local_time: str
    requested_date: str
    forecast_date: str
    forecast_is_exact: bool
    forecast_delta_days: int
    condition: str
    temperature_c: float | None
    wind_kph: float | None
    wind_mph: float | None
    precip_mm: float | None
    humidity: int | None
    chance_of_rain: int | None
    chance_of_snow: int | None
    is_day: int | None

    @property
    def weather_location(self) -> str:
        return ", ".join(part for part in (self.location_name, self.region, self.country) if part)

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["weather_location"] = self.weather_location
        row["weather_location_query"] = self.location_query
        row["weather_condition"] = self.condition
        row["weather_temp_c"] = self.temperature_c
        row["weather_wind_kph"] = self.wind_kph
        row["weather_wind_mph"] = self.wind_mph
        row["weather_precip_mm"] = self.precip_mm
        row["weather_humidity"] = self.humidity
        row["weather_chance_of_rain"] = self.chance_of_rain
        row["weather_chance_of_snow"] = self.chance_of_snow
        row["weather_forecast_is_exact"] = self.forecast_is_exact
        row["weather_forecast_delta_days"] = self.forecast_delta_days
        return row


def get_weatherapi_key(explicit_key: str | None = None) -> str:
    key = (explicit_key or os.getenv("WEATHERAPI_KEY") or "").strip()
    if not key:
        raise RuntimeError("Missing WEATHERAPI_KEY. Paste a real key in the app or set an environment variable.")
    if key.lower() in PLACEHOLDER_KEYS or key.lower().startswith("your_"):
        raise RuntimeError("Invalid WEATHERAPI_KEY placeholder. Replace it with a real WeatherAPI key before running weather enrichment.")
    return key


def _parse_date(value: str | None) -> date:
    if not value:
        return datetime.now(timezone.utc).date()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return datetime.now(timezone.utc).date()


def _days_until(target: date) -> int:
    today = datetime.now(timezone.utc).date()
    return max(1, min(MAX_FORECAST_DAYS, (target - today).days + 1))


def _number(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _select_forecast_day(forecast_days: list[Mapping[str, Any]], target_date: date) -> Mapping[str, Any] | None:
    if not forecast_days:
        return None
    exact = [item for item in forecast_days if str(item.get("date", "")) == target_date.isoformat()]
    if exact:
        return exact[0]

    def distance(item: Mapping[str, Any]) -> int:
        try:
            item_date = date.fromisoformat(str(item.get("date", "")))
            return abs((item_date - target_date).days)
        except ValueError:
            return 9999

    return min(forecast_days, key=distance)


def fetch_weather_snapshot(api_key: str, location: str, event_time_iso: str | None = None) -> WeatherSnapshot:
    target_date = _parse_date(event_time_iso)
    params = {
        "key": get_weatherapi_key(api_key),
        "q": location,
        "days": _days_until(target_date),
        "aqi": "no",
        "alerts": "no",
    }
    response = requests.get(f"{WEATHERAPI_HOST}/forecast.json", params=params, timeout=20)
    response.raise_for_status()
    payload: Mapping[str, Any] = response.json()
    location_payload = payload.get("location", {})
    current = payload.get("current", {})
    forecast_days = payload.get("forecast", {}).get("forecastday", [])
    chosen_day = _select_forecast_day(forecast_days, target_date)
    day = chosen_day.get("day", {}) if chosen_day else {}
    condition = (day.get("condition") or current.get("condition") or {}).get("text", "")
    forecast_date = str(chosen_day.get("date", target_date.isoformat()) if chosen_day else target_date.isoformat())
    try:
        forecast_delta = abs((date.fromisoformat(forecast_date) - target_date).days)
    except ValueError:
        forecast_delta = 9999
    return WeatherSnapshot(
        location_query=location,
        location_name=str(location_payload.get("name", "")),
        region=str(location_payload.get("region", "")),
        country=str(location_payload.get("country", "")),
        local_time=str(location_payload.get("localtime", "")),
        requested_date=target_date.isoformat(),
        forecast_date=forecast_date,
        forecast_is_exact=forecast_delta == 0,
        forecast_delta_days=forecast_delta,
        condition=str(condition),
        temperature_c=_number(day.get("avgtemp_c") if day else current.get("temp_c")),
        wind_kph=_number(day.get("maxwind_kph") if day else current.get("wind_kph")),
        wind_mph=_number(day.get("maxwind_mph") if day else current.get("wind_mph")),
        precip_mm=_number(day.get("totalprecip_mm") if day else current.get("precip_mm")),
        humidity=_integer(day.get("avghumidity") if day else current.get("humidity")),
        chance_of_rain=_integer(day.get("daily_chance_of_rain")),
        chance_of_snow=_integer(day.get("daily_chance_of_snow")),
        is_day=_integer(current.get("is_day")),
    )

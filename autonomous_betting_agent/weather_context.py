from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from dateutil import parser as date_parser


WEATHERAPI_BASE_URL = "https://api.weatherapi.com/v1/forecast.json"

# These are intentionally broad, practical defaults. They let ARA attach weather
# context even when an odds feed only gives team names instead of stadium data.
CITY_HINTS = {
    # MLB / common US teams
    "arizona": "Phoenix, Arizona", "diamondbacks": "Phoenix, Arizona",
    "atlanta": "Atlanta, Georgia", "braves": "Atlanta, Georgia", "falcons": "Atlanta, Georgia", "united": "Atlanta, Georgia",
    "baltimore": "Baltimore, Maryland", "orioles": "Baltimore, Maryland", "ravens": "Baltimore, Maryland",
    "boston": "Boston, Massachusetts", "red sox": "Boston, Massachusetts", "patriots": "Foxborough, Massachusetts",
    "buffalo": "Buffalo, New York", "bills": "Buffalo, New York",
    "chicago": "Chicago, Illinois", "cubs": "Chicago, Illinois", "white sox": "Chicago, Illinois", "bears": "Chicago, Illinois", "fire": "Chicago, Illinois",
    "cincinnati": "Cincinnati, Ohio", "reds": "Cincinnati, Ohio", "bengals": "Cincinnati, Ohio",
    "cleveland": "Cleveland, Ohio", "guardians": "Cleveland, Ohio", "browns": "Cleveland, Ohio",
    "colorado": "Denver, Colorado", "rockies": "Denver, Colorado", "broncos": "Denver, Colorado", "rapids": "Commerce City, Colorado",
    "dallas": "Dallas, Texas", "cowboys": "Arlington, Texas", "rangers": "Arlington, Texas", "fc dallas": "Frisco, Texas",
    "detroit": "Detroit, Michigan", "tigers": "Detroit, Michigan", "lions": "Detroit, Michigan",
    "houston": "Houston, Texas", "astros": "Houston, Texas", "texans": "Houston, Texas", "dynamo": "Houston, Texas",
    "kansas city": "Kansas City, Missouri", "royals": "Kansas City, Missouri", "chiefs": "Kansas City, Missouri",
    "los angeles": "Los Angeles, California", "dodgers": "Los Angeles, California", "angels": "Anaheim, California", "rams": "Inglewood, California", "chargers": "Inglewood, California", "galaxy": "Carson, California", "lafc": "Los Angeles, California",
    "miami": "Miami, Florida", "marlins": "Miami, Florida", "dolphins": "Miami Gardens, Florida", "inter miami": "Fort Lauderdale, Florida",
    "milwaukee": "Milwaukee, Wisconsin", "brewers": "Milwaukee, Wisconsin",
    "minnesota": "Minneapolis, Minnesota", "twins": "Minneapolis, Minnesota", "vikings": "Minneapolis, Minnesota", "united fc": "Saint Paul, Minnesota",
    "new england": "Foxborough, Massachusetts", "revolution": "Foxborough, Massachusetts",
    "new york": "New York, New York", "yankees": "Bronx, New York", "mets": "Queens, New York", "giants": "East Rutherford, New Jersey", "jets": "East Rutherford, New Jersey", "nycfc": "New York, New York", "red bulls": "Harrison, New Jersey",
    "oakland": "Oakland, California", "athletics": "Sacramento, California", "a's": "Sacramento, California",
    "philadelphia": "Philadelphia, Pennsylvania", "phillies": "Philadelphia, Pennsylvania", "eagles": "Philadelphia, Pennsylvania", "union": "Chester, Pennsylvania",
    "pittsburgh": "Pittsburgh, Pennsylvania", "pirates": "Pittsburgh, Pennsylvania", "steelers": "Pittsburgh, Pennsylvania",
    "san diego": "San Diego, California", "padres": "San Diego, California",
    "san francisco": "San Francisco, California", "giants baseball": "San Francisco, California", "49ers": "Santa Clara, California", "earthquakes": "San Jose, California",
    "seattle": "Seattle, Washington", "mariners": "Seattle, Washington", "seahawks": "Seattle, Washington", "sounders": "Seattle, Washington",
    "st louis": "St. Louis, Missouri", "cardinals": "St. Louis, Missouri", "city sc": "St. Louis, Missouri",
    "tampa bay": "Tampa, Florida", "rays": "St. Petersburg, Florida", "buccaneers": "Tampa, Florida",
    "texas": "Austin, Texas", "longhorns": "Austin, Texas",
    "toronto": "Toronto, Ontario", "blue jays": "Toronto, Ontario", "toronto fc": "Toronto, Ontario",
    "washington": "Washington, DC", "nationals": "Washington, DC", "commanders": "Landover, Maryland", "dc united": "Washington, DC",
    # Countries / soccer defaults
    "mexico": "Mexico City, Mexico", "south africa": "Johannesburg, South Africa", "south korea": "Seoul, South Korea", "czechia": "Prague, Czechia",
    "canada": "Toronto, Ontario", "qatar": "Doha, Qatar", "switzerland": "Zurich, Switzerland", "brazil": "Rio de Janeiro, Brazil", "morocco": "Rabat, Morocco", "haiti": "Port-au-Prince, Haiti", "scotland": "Glasgow, Scotland",
    "australia": "Sydney, Australia", "turkey": "Istanbul, Turkey", "germany": "Berlin, Germany", "curacao": "Willemstad, Curacao", "netherlands": "Amsterdam, Netherlands", "japan": "Tokyo, Japan", "ecuador": "Quito, Ecuador", "sweden": "Stockholm, Sweden", "tunisia": "Tunis, Tunisia",
}

OUTDOOR_SPORT_TERMS = [
    "baseball", "mlb", "football", "nfl", "ncaaf", "soccer", "fifa", "world cup",
    "rugby", "cricket", "tennis", "golf", "aussie", "afl", "formula", "nascar",
]
INDOOR_SPORT_TERMS = ["basketball", "nba", "wnba", "hockey", "nhl", "mma", "ufc", "boxing"]


@dataclass
class WeatherSummary:
    location: str
    local_time: str
    condition: str
    temp_f: float | None
    feelslike_f: float | None
    wind_mph: float | None
    wind_dir: str
    gust_mph: float | None
    precip_in: float | None
    humidity: int | None
    chance_of_rain: int | None
    chance_of_snow: int | None
    weather_risk: int
    weather_notes: list[str]


def clean(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").replace(".", " ").replace("'", "").split())


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def is_weather_relevant(sport_text: str) -> bool:
    text = clean(sport_text)
    if any(term in text for term in INDOOR_SPORT_TERMS):
        return False
    return any(term in text for term in OUTDOOR_SPORT_TERMS)


def infer_weather_location(home_team: str, away_team: str = "", sport_text: str = "") -> str:
    text = clean(f"{home_team} {away_team} {sport_text}")
    home = clean(home_team)
    # Prefer the home side, because weather matters at the venue.
    for key, location in CITY_HINTS.items():
        if key in home:
            return location
    for key, location in CITY_HINTS.items():
        if key in text:
            return location
    return home_team or away_team or "New York"


def fetch_weather(api_key: str, location: str, kickoff_iso: str | None = None) -> WeatherSummary:
    """Fetch current/forecast weather from WeatherAPI.com.

    WeatherAPI free tier supports forecast endpoints. For dates beyond the forecast
    window, this function falls back to current conditions.
    """
    params = {
        "key": api_key,
        "q": location,
        "days": 3,
        "aqi": "no",
        "alerts": "no",
    }
    response = requests.get(WEATHERAPI_BASE_URL, params=params, timeout=12)
    response.raise_for_status()
    payload = response.json()
    return summarize_weather(payload, kickoff_iso)


def summarize_weather(payload: dict[str, Any], kickoff_iso: str | None = None) -> WeatherSummary:
    location_name = ", ".join(
        part for part in [
            payload.get("location", {}).get("name"),
            payload.get("location", {}).get("region"),
            payload.get("location", {}).get("country"),
        ] if part
    ) or "unknown"

    current = payload.get("current", {}) or {}
    forecast_hour = pick_forecast_hour(payload, kickoff_iso) if kickoff_iso else None
    source = forecast_hour or current

    condition = ((source.get("condition") or {}).get("text") or "Unknown")
    temp_f = safe_float(source.get("temp_f"))
    feelslike_f = safe_float(source.get("feelslike_f"))
    wind_mph = safe_float(source.get("wind_mph"))
    wind_dir = str(source.get("wind_dir") or "")
    gust_mph = safe_float(source.get("gust_mph"))
    precip_in = safe_float(source.get("precip_in"))
    humidity = safe_int(source.get("humidity"))
    chance_of_rain = safe_int(source.get("chance_of_rain"))
    chance_of_snow = safe_int(source.get("chance_of_snow"))
    local_time = str(source.get("time") or payload.get("location", {}).get("localtime") or "")

    weather_risk, weather_notes = score_weather_risk(
        condition=condition,
        temp_f=temp_f,
        wind_mph=wind_mph,
        gust_mph=gust_mph,
        precip_in=precip_in,
        chance_of_rain=chance_of_rain,
        chance_of_snow=chance_of_snow,
    )

    return WeatherSummary(
        location=location_name,
        local_time=local_time,
        condition=condition,
        temp_f=temp_f,
        feelslike_f=feelslike_f,
        wind_mph=wind_mph,
        wind_dir=wind_dir,
        gust_mph=gust_mph,
        precip_in=precip_in,
        humidity=humidity,
        chance_of_rain=chance_of_rain,
        chance_of_snow=chance_of_snow,
        weather_risk=weather_risk,
        weather_notes=weather_notes,
    )


def pick_forecast_hour(payload: dict[str, Any], kickoff_iso: str | None) -> dict[str, Any] | None:
    try:
        kickoff = date_parser.parse(str(kickoff_iso))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
    except Exception:
        return None

    hours: list[dict[str, Any]] = []
    for day in payload.get("forecast", {}).get("forecastday", []) or []:
        hours.extend(day.get("hour", []) or [])
    if not hours:
        return None

    best_hour = None
    best_delta = None
    for hour in hours:
        try:
            epoch = int(hour.get("time_epoch"))
            hour_dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        except Exception:
            continue
        delta = abs((hour_dt - kickoff.astimezone(timezone.utc)).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_hour = hour
    return best_hour


def score_weather_risk(
    condition: str,
    temp_f: float | None,
    wind_mph: float | None,
    gust_mph: float | None,
    precip_in: float | None,
    chance_of_rain: int | None,
    chance_of_snow: int | None,
) -> tuple[int, list[str]]:
    risk = 0
    notes: list[str] = []
    condition_text = condition.lower()

    if any(term in condition_text for term in ["thunder", "storm"]):
        risk += 20
        notes.append("storm risk")
    if any(term in condition_text for term in ["rain", "drizzle", "shower"]):
        risk += 10
        notes.append("rain")
    if any(term in condition_text for term in ["snow", "sleet", "ice", "blizzard"]):
        risk += 15
        notes.append("snow/ice")

    if chance_of_rain is not None and chance_of_rain >= 60:
        risk += 10
        notes.append(f"rain chance {chance_of_rain}%")
    if chance_of_snow is not None and chance_of_snow >= 40:
        risk += 12
        notes.append(f"snow chance {chance_of_snow}%")
    if precip_in is not None and precip_in >= 0.10:
        risk += 8
        notes.append(f"precip {precip_in:.2f} in")
    if wind_mph is not None and wind_mph >= 15:
        risk += 8
        notes.append(f"wind {wind_mph:.0f} mph")
    if gust_mph is not None and gust_mph >= 25:
        risk += 8
        notes.append(f"gusts {gust_mph:.0f} mph")
    if temp_f is not None and temp_f >= 90:
        risk += 6
        notes.append(f"heat {temp_f:.0f}F")
    if temp_f is not None and temp_f <= 35:
        risk += 6
        notes.append(f"cold {temp_f:.0f}F")

    return min(50, risk), notes or ["normal weather"]


def weather_note(summary: WeatherSummary | None) -> str:
    if summary is None:
        return ""
    return f"{summary.condition}, {summary.temp_f:.0f}F, wind {summary.wind_mph:.0f} mph, risk {summary.weather_risk}/50" if summary.temp_f is not None and summary.wind_mph is not None else f"{summary.condition}, risk {summary.weather_risk}/50"


def summary_to_dict(summary: WeatherSummary) -> dict[str, Any]:
    return {
        "location": summary.location,
        "local_time": summary.local_time,
        "condition": summary.condition,
        "temp_f": summary.temp_f,
        "feelslike_f": summary.feelslike_f,
        "wind_mph": summary.wind_mph,
        "wind_dir": summary.wind_dir,
        "gust_mph": summary.gust_mph,
        "precip_in": summary.precip_in,
        "humidity": summary.humidity,
        "chance_of_rain": summary.chance_of_rain,
        "chance_of_snow": summary.chance_of_snow,
        "weather_risk": summary.weather_risk,
        "weather_notes": "; ".join(summary.weather_notes),
    }

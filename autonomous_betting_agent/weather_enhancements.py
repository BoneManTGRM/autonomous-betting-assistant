from __future__ import annotations

from dataclasses import dataclass
from typing import Any


NFL_VENUES = {
    "jacksonville jaguars": ("Jacksonville, Florida", "outdoor", "EverBank Stadium is outdoor"),
    "jaguars": ("Jacksonville, Florida", "outdoor", "EverBank Stadium is outdoor"),
    "cleveland browns": ("Cleveland, Ohio", "outdoor", "Cleveland Browns Stadium is outdoor"),
    "browns": ("Cleveland, Ohio", "outdoor", "Cleveland Browns Stadium is outdoor"),
    "buffalo bills": ("Buffalo, New York", "outdoor", "Highmark Stadium is outdoor; wind/snow can matter"),
    "bills": ("Buffalo, New York", "outdoor", "Highmark Stadium is outdoor; wind/snow can matter"),
    "chicago bears": ("Chicago, Illinois", "outdoor", "Soldier Field is outdoor; wind can matter"),
    "bears": ("Chicago, Illinois", "outdoor", "Soldier Field is outdoor; wind can matter"),
    "green bay packers": ("Green Bay, Wisconsin", "outdoor", "Lambeau Field is outdoor; cold/wind can matter"),
    "packers": ("Green Bay, Wisconsin", "outdoor", "Lambeau Field is outdoor; cold/wind can matter"),
    "new england patriots": ("Foxborough, Massachusetts", "outdoor", "Gillette Stadium is outdoor; wind/cold can matter"),
    "patriots": ("Foxborough, Massachusetts", "outdoor", "Gillette Stadium is outdoor; wind/cold can matter"),
    "arizona cardinals": ("Glendale, Arizona", "retractable_roof", "State Farm Stadium roof can reduce weather impact"),
    "atlanta falcons": ("Atlanta, Georgia", "retractable_roof", "Mercedes-Benz Stadium roof can reduce weather impact"),
    "dallas cowboys": ("Arlington, Texas", "retractable_roof", "AT&T Stadium roof can reduce weather impact"),
    "houston texans": ("Houston, Texas", "retractable_roof", "NRG Stadium roof can reduce weather impact"),
    "indianapolis colts": ("Indianapolis, Indiana", "retractable_roof", "Lucas Oil Stadium roof can reduce weather impact"),
    "cardinals": ("Glendale, Arizona", "retractable_roof", "State Farm Stadium roof can reduce weather impact"),
    "falcons": ("Atlanta, Georgia", "retractable_roof", "Mercedes-Benz Stadium roof can reduce weather impact"),
    "cowboys": ("Arlington, Texas", "retractable_roof", "AT&T Stadium roof can reduce weather impact"),
    "texans": ("Houston, Texas", "retractable_roof", "NRG Stadium roof can reduce weather impact"),
    "colts": ("Indianapolis, Indiana", "retractable_roof", "Lucas Oil Stadium roof can reduce weather impact"),
    "detroit lions": ("Detroit, Michigan", "indoor", "Ford Field is indoor"),
    "las vegas raiders": ("Las Vegas, Nevada", "indoor", "Allegiant Stadium is indoor"),
    "los angeles rams": ("Inglewood, California", "indoor", "SoFi Stadium is roofed; weather impact is usually reduced"),
    "los angeles chargers": ("Inglewood, California", "indoor", "SoFi Stadium is roofed; weather impact is usually reduced"),
    "minnesota vikings": ("Minneapolis, Minnesota", "indoor", "U.S. Bank Stadium is indoor"),
    "new orleans saints": ("New Orleans, Louisiana", "indoor", "Caesars Superdome is indoor"),
    "lions": ("Detroit, Michigan", "indoor", "Ford Field is indoor"),
    "raiders": ("Las Vegas, Nevada", "indoor", "Allegiant Stadium is indoor"),
    "rams": ("Inglewood, California", "indoor", "SoFi Stadium is roofed; weather impact is usually reduced"),
    "chargers": ("Inglewood, California", "indoor", "SoFi Stadium is roofed; weather impact is usually reduced"),
    "vikings": ("Minneapolis, Minnesota", "indoor", "U.S. Bank Stadium is indoor"),
    "saints": ("New Orleans, Louisiana", "indoor", "Caesars Superdome is indoor"),
}


@dataclass
class VenueDecision:
    location_override: str
    roof_type: str
    venue_note: str
    matched_term: str


def clean(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").replace(".", " ").replace("'", "").split())


def nfl_venue_decision(home_team: str = "", sport_text: str = "") -> VenueDecision:
    text = clean(home_team)
    sport = clean(sport_text)
    is_football = any(term in sport for term in ["nfl", "football"])
    if not is_football:
        return VenueDecision("", "outdoor_or_unknown", "No NFL venue rule applied", "")
    for key in sorted(NFL_VENUES, key=len, reverse=True):
        if key in text:
            location, roof_type, note = NFL_VENUES[key]
            return VenueDecision(location, roof_type, note, key)
    return VenueDecision("", "outdoor_or_unknown", "No NFL venue rule matched", "")


def effective_risk(raw_risk: int, roof_type: str) -> int:
    try:
        raw = int(raw_risk or 0)
    except Exception:
        raw = 0
    if roof_type == "indoor":
        return min(8, round(raw * 0.20))
    if roof_type == "retractable_roof":
        return min(18, round(raw * 0.45))
    return raw


def weather_action(summary: Any, sport_text: str = "", roof_type: str = "outdoor_or_unknown") -> str:
    risk = effective_risk(getattr(summary, "weather_risk", 0), roof_type)
    sport = clean(sport_text)
    wind = getattr(summary, "wind_mph", None) or 0
    gusts = getattr(summary, "gust_mph", None) or 0
    rain = getattr(summary, "chance_of_rain", None) or 0
    snow = getattr(summary, "chance_of_snow", None) or 0
    condition = clean(getattr(summary, "condition", ""))
    if roof_type == "indoor":
        return "Dome/indoor: weather mostly neutral"
    if roof_type == "retractable_roof":
        return "Roof status watch: verify roof before weighting weather"
    if risk >= 25:
        return "High-variance weather game"
    if any(term in sport for term in ["baseball", "mlb"]) and (wind >= 15 or gusts >= 25):
        return "MLB totals caution: check wind direction"
    if any(term in sport for term in ["football", "nfl", "ncaaf"]) and (wind >= 15 or gusts >= 25):
        return "Football passing/kicking wind caution"
    if rain >= 60 or "rain" in condition:
        return "Rain/delay caution"
    if snow >= 40 or "snow" in condition:
        return "Snow/cold-weather caution"
    if risk >= 12:
        return "Weather watch"
    return "No major weather concern"


def market_weather_weight(sport_text: str = "", market_text: str = "", roof_type: str = "outdoor_or_unknown") -> str:
    sport = clean(sport_text)
    market = clean(market_text)
    if roof_type == "indoor":
        return "low"
    if any(term in market for term in ["total", "over", "under"]):
        if any(term in sport for term in ["baseball", "mlb", "football", "nfl", "ncaaf"]):
            return "high"
        return "medium"
    if any(term in market for term in ["spread", "handicap"]):
        return "medium"
    if any(term in sport for term in ["soccer", "fifa", "world cup", "tennis", "wta", "atp"]):
        return "medium"
    return "low"

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

SPORT_WEATHER_SENSITIVITY = {
    "baseball": 1.25,
    "mlb": 1.25,
    "football": 1.15,
    "nfl": 1.15,
    "soccer": 1.10,
    "tennis": 1.05,
    "golf": 1.20,
    "basketball": 0.20,
    "nba": 0.20,
    "wnba": 0.20,
    "hockey": 0.15,
    "nhl": 0.15,
}

INDOOR_HINTS = {"indoor", "dome", "arena", "closed roof", "retractable closed"}
OUTDOOR_HINTS = {"outdoor", "open", "stadium", "pitch", "park"}


@dataclass(frozen=True)
class EnvironmentRisk:
    weather_risk_score: float
    weather_flag: str
    weather_reason: str
    weather_bet_adjustment: str


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lowered = {str(key).lower().replace(" ", "_").replace("-", "_"): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower().replace(" ", "_").replace("-", "_"))
        if value not in (None, ""):
            return value
    return ""


def _is_indoor(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(_first(row, ("venue_type", "stadium_type", "roof", "venue", "stadium"))).lower().split())
    return any(hint in text for hint in INDOOR_HINTS) and not any(hint in text for hint in OUTDOOR_HINTS)


def _sport_multiplier(sport: str) -> float:
    text = str(sport or "").strip().lower()
    return SPORT_WEATHER_SENSITIVITY.get(text, 1.0)


def score_environment(row: Mapping[str, Any], *, sport: str = "") -> EnvironmentRisk:
    if _is_indoor(row):
        return EnvironmentRisk(95.0, "LOW", "Indoor/covered venue: weather impact reduced.", "NO_ADJUSTMENT")

    sport_value = sport or str(_first(row, ("sport", "league")))
    mult = _sport_multiplier(sport_value)
    temp_f = _float(_first(row, ("temp_f", "temperature_f", "temperature")))
    temp_c = _float(_first(row, ("temp_c", "temperature_c")))
    wind_mph = _float(_first(row, ("wind_mph", "wind_speed_mph")))
    wind_kph = _float(_first(row, ("wind_kph", "wind_speed_kph")))
    gust_mph = _float(_first(row, ("gust_mph", "wind_gust_mph")))
    precip_mm = _float(_first(row, ("precip_mm", "rain_mm", "precipitation_mm")))
    humidity = _float(_first(row, ("humidity", "relative_humidity")))

    if temp_f is None and temp_c is not None:
        temp_f = temp_c * 9 / 5 + 32
    if wind_mph is None and wind_kph is not None:
        wind_mph = wind_kph * 0.621371

    penalties: list[tuple[float, str]] = []
    if temp_f is not None:
        if temp_f <= 25 or temp_f >= 95:
            penalties.append((22, "extreme temperature"))
        elif temp_f <= 38 or temp_f >= 88:
            penalties.append((10, "moderate temperature edge"))
    if wind_mph is not None:
        if wind_mph >= 22:
            penalties.append((30, "strong sustained wind"))
        elif wind_mph >= 14:
            penalties.append((14, "moderate wind"))
    if gust_mph is not None and gust_mph >= 30:
        penalties.append((16, "high wind gusts"))
    if precip_mm is not None:
        if precip_mm >= 6:
            penalties.append((22, "heavy precipitation"))
        elif precip_mm > 0:
            penalties.append((8, "light precipitation"))
    if humidity is not None and humidity >= 90 and temp_f is not None and temp_f >= 80:
        penalties.append((8, "high heat humidity"))

    adjusted_penalty = sum(value for value, _ in penalties) * mult
    score = round(max(0.0, min(100.0, 100.0 - adjusted_penalty)), 2)
    reasons = [reason for _, reason in penalties] or ["no major weather concern"]
    if score >= 80:
        flag = "LOW"
        adjustment = "NO_ADJUSTMENT"
    elif score >= 60:
        flag = "WATCH"
        adjustment = "REDUCE_CONFIDENCE"
    else:
        flag = "HIGH"
        adjustment = "REJECT_OR_WAIT"
    return EnvironmentRisk(score, flag, "; ".join(reasons), adjustment)


def enrich_rows_with_environment(rows: list[Mapping[str, Any]], *, sport: str = "") -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        risk = score_environment(row, sport=sport)
        enriched = dict(row)
        enriched.update({
            "weather_risk_score": str(risk.weather_risk_score),
            "weather_flag": risk.weather_flag,
            "weather_reason": risk.weather_reason,
            "weather_bet_adjustment": risk.weather_bet_adjustment,
        })
        output.append(enriched)
    return output

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Mapping

from .api_clients import WeatherAPIClient, WeatherAPIConfig
from .environment_intelligence import score_environment
from .sportsdataio import SportsDataIOClient, SportsDataIOConfig


def _clean(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").replace("_", " ").split())


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
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


def _similarity(left: Any, right: Any) -> float:
    left_clean, right_clean = _clean(left), _clean(right)
    if not left_clean or not right_clean:
        return 0.0
    if left_clean == right_clean:
        return 1.0
    if left_clean in right_clean or right_clean in left_clean:
        return 0.92
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def sportsdataio_sport_from_odds(sport_key: str, sport_title: str = "") -> str | None:
    text = _clean(f"{sport_key} {sport_title}")
    if "wnba" in text:
        return "wnba"
    if "nfl" in text or "americanfootball nfl" in text:
        return "nfl"
    if "nba" in text or "basketball nba" in text:
        return "nba"
    if "mlb" in text or "baseball mlb" in text:
        return "mlb"
    if "nhl" in text or "icehockey nhl" in text:
        return "nhl"
    if "ncaaf" in text or "college football" in text or "americanfootball_ncaaf" in text:
        return "cfb"
    if "ncaab" in text or "college basketball" in text or "basketball_ncaab" in text:
        return "cbb"
    if "soccer" in text:
        return "soccer"
    return None


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        for value in payload.values():
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, Mapping)]
        return [dict(payload)]
    return []


def _team_aliases(record: Mapping[str, Any]) -> set[str]:
    aliases: set[str] = set()
    simple_names = (
        "Name",
        "FullName",
        "TeamName",
        "Team",
        "City",
        "Key",
        "TeamKey",
        "School",
        "ShortName",
    )
    for name in simple_names:
        value = _first(record, (name,))
        if value:
            aliases.add(_clean(value))
    city = _first(record, ("City", "School"))
    nickname = _first(record, ("Name", "TeamName"))
    if city and nickname:
        aliases.add(_clean(f"{city} {nickname}"))
    return {alias for alias in aliases if alias}


def _match_team(team: str, teams: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not team or not teams:
        return None
    best_score = 0.0
    best_record: dict[str, Any] | None = None
    for record in teams:
        aliases = _team_aliases(record)
        score = max((_similarity(team, alias) for alias in aliases), default=0.0)
        if score > best_score:
            best_score = score
            best_record = record
    return best_record if best_score >= 0.72 else None


def _win_pct(record: Mapping[str, Any] | None) -> float | None:
    if not record:
        return None
    direct = _float(_first(record, ("Percentage", "WinningPercentage", "WinPercentage", "Pct", "WinPct")))
    if direct is not None:
        if direct > 1.0:
            direct /= 100.0
        if 0.0 <= direct <= 1.0:
            return direct
    wins = _float(_first(record, ("Wins", "Win", "GamesWon")))
    losses = _float(_first(record, ("Losses", "Loss", "GamesLost")))
    ties = _float(_first(record, ("Ties", "Tie"))) or 0.0
    if wins is None or losses is None:
        return None
    total = wins + losses + ties
    if total <= 0:
        return None
    return (wins + 0.5 * ties) / total


def _stats_probability_for_pick(home_record: Mapping[str, Any] | None, away_record: Mapping[str, Any] | None, home_team: str, away_team: str, pick_name: str) -> tuple[float | None, str]:
    home_pct = _win_pct(home_record)
    away_pct = _win_pct(away_record)
    if home_pct is None and away_pct is None:
        return None, "SportsDataIO team records did not include usable win/loss percentages"
    if home_pct is not None and away_pct is not None:
        edge = max(-0.35, min(0.35, home_pct - away_pct))
        home_probability = max(0.35, min(0.75, 0.50 + edge * 0.45))
    elif home_pct is not None:
        home_probability = max(0.38, min(0.72, 0.50 + (home_pct - 0.50) * 0.35))
    else:
        away_probability = max(0.38, min(0.72, 0.50 + ((away_pct or 0.50) - 0.50) * 0.35))
        home_probability = 1.0 - away_probability

    if _similarity(pick_name, home_team) >= _similarity(pick_name, away_team):
        return round(home_probability, 6), "SportsDataIO team record strength"
    return round(1.0 - home_probability, 6), "SportsDataIO team record strength"


def _team_keys(record: Mapping[str, Any] | None) -> set[str]:
    if not record:
        return set()
    names = ("Team", "TeamKey", "Key", "Name", "FullName", "City", "TeamID", "GlobalTeamID")
    return {_clean(_first(record, (name,))) for name in names if _first(record, (name,))}


def _injury_team_match(injury: Mapping[str, Any], team_record: Mapping[str, Any] | None) -> bool:
    keys = _team_keys(team_record)
    if not keys:
        return False
    injury_values = {
        _clean(_first(injury, ("Team",))),
        _clean(_first(injury, ("TeamKey",))),
        _clean(_first(injury, ("TeamID",))),
        _clean(_first(injury, ("GlobalTeamID",))),
    }
    return bool(keys & {value for value in injury_values if value})


def _injury_score(injuries: list[dict[str, Any]], picked_record: Mapping[str, Any] | None) -> tuple[float | None, str, int]:
    if picked_record is None:
        return None, "SportsDataIO injuries skipped because picked team was not matched", 0
    team_injuries = [injury for injury in injuries if _injury_team_match(injury, picked_record)]
    if not team_injuries:
        return 100.0, "SportsDataIO injuries: no listed injuries for picked team", 0
    severe = 0
    watch = 0
    for injury in team_injuries:
        text = _clean(" ".join(str(_first(injury, (name,))) for name in ("Status", "InjuryStatus", "GameStatus", "Practice", "BodyPart")))
        if any(token in text for token in ("out", "injured reserve", "ir", "doubtful", "inactive")):
            severe += 1
        elif any(token in text for token in ("questionable", "probable", "limited")):
            watch += 1
    score = max(45.0, 100.0 - severe * 7.5 - watch * 2.5)
    reason = f"SportsDataIO injuries: {len(team_injuries)} listed, {severe} severe, {watch} watch"
    return round(score, 2), reason, len(team_injuries)


def _event_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _forecast_days_for(start: datetime | None) -> int:
    if start is None:
        return 1
    delta_days = (start.date() - datetime.now(timezone.utc).date()).days
    return max(1, min(10, delta_days + 1))


def _location_from_team(record: Mapping[str, Any] | None, fallback_team: str) -> str:
    if not record:
        return fallback_team
    stadium_city = _first(record, ("StadiumDetails_City", "Stadium_City", "VenueCity"))
    stadium_state = _first(record, ("StadiumDetails_State", "Stadium_State", "VenueState"))
    city = _first(record, ("City", "School"))
    state = _first(record, ("State", "Province"))
    country = _first(record, ("Country",))
    if stadium_city:
        return ", ".join(str(part) for part in (stadium_city, stadium_state or country) if part)
    if city:
        return ", ".join(str(part) for part in (city, state or country) if part)
    return fallback_team


def _weather_row(payload: Mapping[str, Any], start: datetime | None) -> dict[str, Any]:
    selected: Mapping[str, Any] = {}
    forecast = payload.get("forecast") if isinstance(payload.get("forecast"), Mapping) else {}
    days = forecast.get("forecastday") if isinstance(forecast.get("forecastday"), list) else []
    target_date = start.date().isoformat() if start else ""
    for day in days:
        if not isinstance(day, Mapping):
            continue
        if target_date and str(day.get("date", "")) != target_date:
            continue
        hours = day.get("hour") if isinstance(day.get("hour"), list) else []
        if hours and start:
            target_hour = start.hour
            hourly = [item for item in hours if isinstance(item, Mapping)]
            selected = min(hourly, key=lambda item: abs(int(str(item.get("time", "00:00"))[-5:-3] or 0) - target_hour), default={})
        if not selected:
            selected = day.get("day") if isinstance(day.get("day"), Mapping) else {}
        break
    if not selected:
        selected = payload.get("current") if isinstance(payload.get("current"), Mapping) else {}
    return {
        "temp_c": selected.get("temp_c") or selected.get("avgtemp_c"),
        "temp_f": selected.get("temp_f") or selected.get("avgtemp_f"),
        "wind_kph": selected.get("wind_kph") or selected.get("maxwind_kph"),
        "wind_mph": selected.get("wind_mph") or selected.get("maxwind_mph"),
        "gust_mph": selected.get("gust_mph"),
        "precip_mm": selected.get("precip_mm") or selected.get("totalprecip_mm"),
        "humidity": selected.get("humidity") or selected.get("avghumidity"),
        "condition_text": (selected.get("condition") or {}).get("text", "") if isinstance(selected.get("condition"), Mapping) else "",
    }


@dataclass
class LiveAPIContextBuilder:
    sportsdataio_key: str = ""
    weatherapi_key: str = ""
    sportsdataio_client_factory: Callable[[str], SportsDataIOClient] | None = None
    weather_client: WeatherAPIClient | None = None
    sportsdataio_auth_mode: str = "header"
    _sports_clients: dict[str, SportsDataIOClient] = field(default_factory=dict)
    _teams_cache: dict[str, tuple[list[dict[str, Any]], str]] = field(default_factory=dict)
    _injury_cache: dict[str, tuple[list[dict[str, Any]], str]] = field(default_factory=dict)
    _weather_cache: dict[tuple[str, int], tuple[dict[str, Any], str]] = field(default_factory=dict)

    def _sports_client(self, sport: str) -> SportsDataIOClient | None:
        if not self.sportsdataio_key and self.sportsdataio_client_factory is None:
            return None
        if sport not in self._sports_clients:
            if self.sportsdataio_client_factory is not None:
                self._sports_clients[sport] = self.sportsdataio_client_factory(sport)
            else:
                self._sports_clients[sport] = SportsDataIOClient(
                    SportsDataIOConfig(api_key=self.sportsdataio_key, sport=sport, auth_mode=self.sportsdataio_auth_mode)
                )
        return self._sports_clients[sport]

    def _weather_client(self) -> WeatherAPIClient | None:
        if self.weather_client is not None:
            return self.weather_client
        if not self.weatherapi_key:
            return None
        self.weather_client = WeatherAPIClient(WeatherAPIConfig(api_key=self.weatherapi_key))
        return self.weather_client

    def _teams(self, sport: str) -> tuple[list[dict[str, Any]], str]:
        if sport in self._teams_cache:
            return self._teams_cache[sport]
        client = self._sports_client(sport)
        if client is None:
            result = ([], "not_configured")
        else:
            try:
                result = (_records(client.teams(sport=sport)), "used")
            except Exception as exc:  # pragma: no cover - external API safety
                result = ([], f"error: {exc}")
        self._teams_cache[sport] = result
        return result

    def _injuries(self, sport: str) -> tuple[list[dict[str, Any]], str]:
        if sport in self._injury_cache:
            return self._injury_cache[sport]
        client = self._sports_client(sport)
        if client is None:
            result = ([], "not_configured")
        else:
            try:
                result = (_records(client.raw_endpoint("Injuries", sport=sport, subfeed="scores")), "used")
            except Exception as exc:  # pragma: no cover - external API safety
                result = ([], f"error: {exc}")
        self._injury_cache[sport] = result
        return result

    def _weather(self, location: str, start: datetime | None) -> tuple[dict[str, Any], str]:
        client = self._weather_client()
        days = _forecast_days_for(start)
        key = (_clean(location), days)
        if key in self._weather_cache:
            return self._weather_cache[key]
        if client is None:
            result = ({}, "not_configured")
        elif not location.strip():
            result = ({}, "no_location")
        else:
            try:
                payload = client.forecast(location=location, days=days)
                result = (_weather_row(payload if isinstance(payload, Mapping) else {}, start), "used")
            except Exception as exc:  # pragma: no cover - external API safety
                result = ({}, f"error: {exc}")
        self._weather_cache[key] = result
        return result

    def context_for_event(self, event: Any, *, pick_name: str) -> dict[str, Any]:
        sport_key = str(getattr(event, "sport_key", ""))
        sport_title = str(getattr(event, "sport_title", ""))
        home_team = str(getattr(event, "home_team", ""))
        away_team = str(getattr(event, "away_team", ""))
        start = _event_datetime(str(getattr(event, "commence_time", "")))
        context: dict[str, Any] = {
            "odds_api_source_used": "yes",
            "sportsdataio_source_used": "no",
            "sportsdataio_status": "not_configured" if not self.sportsdataio_key and self.sportsdataio_client_factory is None else "not_supported_sport",
            "stats_source_used": "no",
            "injury_source_used": "no",
            "weather_source_used": "no",
            "weatherapi_status": "not_configured" if not self.weatherapi_key and self.weather_client is None else "no_location",
        }

        sdio_sport = sportsdataio_sport_from_odds(sport_key, sport_title)
        home_record: dict[str, Any] | None = None
        away_record: dict[str, Any] | None = None
        picked_record: dict[str, Any] | None = None
        if sdio_sport:
            teams, teams_status = self._teams(sdio_sport)
            home_record = _match_team(home_team, teams)
            away_record = _match_team(away_team, teams)
            picked_record = home_record if _similarity(pick_name, home_team) >= _similarity(pick_name, away_team) else away_record
            context.update(
                {
                    "sportsdataio_sport": sdio_sport,
                    "sportsdataio_status": teams_status,
                    "sportsdataio_team_metadata_used": "yes" if teams_status == "used" and (home_record or away_record) else "no",
                    "sportsdataio_home_team_matched": "yes" if home_record else "no",
                    "sportsdataio_away_team_matched": "yes" if away_record else "no",
                    "sportsdataio_home_city": _first(home_record or {}, ("City", "School", "StadiumDetails_City")),
                    "sportsdataio_away_city": _first(away_record or {}, ("City", "School", "StadiumDetails_City")),
                }
            )
            stats_probability, stats_reason = _stats_probability_for_pick(home_record, away_record, home_team, away_team, pick_name)
            context["stats_source_reason"] = stats_reason
            if stats_probability is not None:
                context["stats_probability"] = stats_probability
                context["stats_source_used"] = "yes"
                context["sportsdataio_source_used"] = "yes"

            injuries, injuries_status = self._injuries(sdio_sport)
            context["sportsdataio_injuries_status"] = injuries_status
            if injuries_status == "used":
                injury_score, injury_reason, injury_count = _injury_score(injuries, picked_record)
                context["injury_source_reason"] = injury_reason
                context["sportsdataio_picked_team_injury_count"] = injury_count
                if injury_score is not None:
                    context["injury_risk_score"] = injury_score
                    context["injury_source_used"] = "yes"
                    context["sportsdataio_source_used"] = "yes"
            else:
                context["injury_source_reason"] = f"SportsDataIO injuries unavailable: {injuries_status}"
                context["sportsdataio_picked_team_injury_count"] = 0

        location = _location_from_team(home_record, home_team)
        weather_row, weather_status = self._weather(location, start)
        context["weather_location"] = location
        context["weatherapi_status"] = weather_status
        if weather_row and weather_status == "used":
            risk = score_environment({**weather_row, "sport": sport_title or sport_key}, sport=sport_title or sport_key)
            context.update(weather_row)
            context.update(
                {
                    "weather_risk_score": risk.weather_risk_score,
                    "weather_flag": risk.weather_flag,
                    "weather_reason": risk.weather_reason,
                    "weather_bet_adjustment": risk.weather_bet_adjustment,
                    "weather_source_used": "yes",
                }
            )
        return context

"""Optional API-Football client and normalizers.

All functions are safe to call without a key. They return normalized empty data
with warnings instead of crashing the local-first workflow.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from .api_config import get_secret

BASE_URL = "https://v3.football.api-sports.io"


def _missing() -> dict[str, Any]:
    return {"rows": [], "warnings": ["API_FOOTBALL_KEY missing; using local CSV mode."], "source": "api-football"}


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str) and value.endswith("%"):
            value = value[:-1]
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> float | None:
    number = _safe_float(value)
    if number is None:
        return None
    if number > 1:
        number /= 100.0
    return max(0.0, min(1.0, number))


@lru_cache(maxsize=128)
def _request(endpoint: str, params_tuple: tuple[tuple[str, Any], ...]) -> dict[str, Any]:
    key = get_secret("API_FOOTBALL_KEY")
    if not key:
        return _missing()
    params = {k: v for k, v in params_tuple if v not in (None, "")}
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + urlencode(params)
    request = Request(url, headers={"x-apisports-key": key})
    try:
        with urlopen(request, timeout=15) as response:  # nosec - user-configured API endpoint
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"rows": [], "warnings": [f"API-Football request failed for {endpoint}: {exc}"], "source": "api-football"}
    if payload.get("errors"):
        return {"rows": [], "warnings": [f"API-Football returned errors for {endpoint}: {payload.get('errors')}"], "source": "api-football"}
    return {"raw": payload, "warnings": [], "source": "api-football"}


def _call(endpoint: str, **params: Any) -> dict[str, Any]:
    return _request(endpoint, tuple(sorted(params.items())))


def fetch_api_football_fixtures(date: str | None = None, league: str | int | None = None, season: str | int | None = None) -> dict[str, Any]:
    result = _call("fixtures", date=date, league=league, season=season)
    raw_rows = result.get("raw", {}).get("response", [])
    return {"rows": [normalize_api_football_fixture(item) for item in raw_rows], "warnings": result.get("warnings", []), "source": "api-football"}


def fetch_api_football_fixture_statistics(fixture_id: str | int) -> dict[str, Any]:
    result = _call("fixtures/statistics", fixture=fixture_id)
    raw_rows = result.get("raw", {}).get("response", [])
    return {"rows": [normalize_api_football_statistics(item) for item in raw_rows], "warnings": result.get("warnings", []), "source": "api-football"}


def fetch_api_football_lineups(fixture_id: str | int) -> dict[str, Any]:
    result = _call("fixtures/lineups", fixture=fixture_id)
    return {"rows": result.get("raw", {}).get("response", []), "warnings": result.get("warnings", []), "source": "api-football"}


def fetch_api_football_injuries(fixture_id: str | int | None = None, team_id: str | int | None = None) -> dict[str, Any]:
    result = _call("injuries", fixture=fixture_id, team=team_id)
    return {"rows": result.get("raw", {}).get("response", []), "warnings": result.get("warnings", []), "source": "api-football"}


def fetch_api_football_standings(league: str | int, season: str | int) -> dict[str, Any]:
    result = _call("standings", league=league, season=season)
    return {"rows": result.get("raw", {}).get("response", []), "warnings": result.get("warnings", []), "source": "api-football"}


def fetch_api_football_odds(fixture_id: str | int | None = None, league: str | int | None = None, date: str | None = None) -> dict[str, Any]:
    result = _call("odds", fixture=fixture_id, league=league, date=date)
    raw_rows = result.get("raw", {}).get("response", [])
    normalized: list[dict[str, Any]] = []
    for item in raw_rows:
        normalized.extend(normalize_api_football_odds(item))
    return {"rows": normalized, "warnings": result.get("warnings", []), "source": "api-football"}


def normalize_api_football_fixture(raw: Mapping[str, Any]) -> dict[str, Any]:
    fixture = raw.get("fixture", {}) if isinstance(raw.get("fixture"), Mapping) else {}
    teams = raw.get("teams", {}) if isinstance(raw.get("teams"), Mapping) else {}
    league = raw.get("league", {}) if isinstance(raw.get("league"), Mapping) else {}
    home = teams.get("home", {}) if isinstance(teams.get("home"), Mapping) else {}
    away = teams.get("away", {}) if isinstance(teams.get("away"), Mapping) else {}
    home_name = str(home.get("name") or "")
    away_name = str(away.get("name") or "")
    return {
        "game": f"{home_name} vs {away_name}".strip(" vs "),
        "sport": "Soccer",
        "league": league.get("name") or league.get("id") or "Soccer",
        "start_time": fixture.get("date"),
        "home_team": home_name,
        "away_team": away_name,
        "fixture_id": fixture.get("id"),
        "lineup_confirmed": bool(raw.get("lineups")),
        "source": "api-football",
    }


def normalize_api_football_statistics(raw: Mapping[str, Any]) -> dict[str, Any]:
    team = raw.get("team", {}) if isinstance(raw.get("team"), Mapping) else {}
    stats = raw.get("statistics", [])
    values: dict[str, Any] = {"team": team.get("name"), "source": "api-football"}
    if isinstance(stats, list):
        for item in stats:
            if not isinstance(item, Mapping):
                continue
            stat_type = str(item.get("type") or "").lower().replace(" ", "_")
            values[stat_type] = item.get("value")
    values["possession_edge"] = _pct(values.get("ball_possession"))
    values["shots_edge"] = _safe_float(values.get("total_shots"))
    values["corner_edge"] = _safe_float(values.get("corner_kicks"))
    values["card_edge"] = (_safe_float(values.get("yellow_cards")) or 0) + (_safe_float(values.get("red_cards")) or 0)
    return values


def normalize_api_football_odds(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    fixture = raw.get("fixture", {}) if isinstance(raw.get("fixture"), Mapping) else {}
    league = raw.get("league", {}) if isinstance(raw.get("league"), Mapping) else {}
    teams = raw.get("teams", {}) if isinstance(raw.get("teams"), Mapping) else {}
    bookmakers = raw.get("bookmakers", [])
    rows: list[dict[str, Any]] = []
    if not isinstance(bookmakers, list):
        return rows
    home = teams.get("home", {}) if isinstance(teams.get("home"), Mapping) else {}
    away = teams.get("away", {}) if isinstance(teams.get("away"), Mapping) else {}
    game = f"{home.get('name', '')} vs {away.get('name', '')}".strip(" vs ")
    for bookmaker in bookmakers:
        if not isinstance(bookmaker, Mapping):
            continue
        for bet in bookmaker.get("bets", []) or []:
            if not isinstance(bet, Mapping):
                continue
            market = bet.get("name")
            for value in bet.get("values", []) or []:
                if not isinstance(value, Mapping):
                    continue
                decimal = _safe_float(value.get("odd"))
                rows.append({
                    "game": game,
                    "sport": "Soccer",
                    "league": league.get("name"),
                    "start_time": fixture.get("date"),
                    "fixture_id": fixture.get("id"),
                    "market": market,
                    "selection": value.get("value"),
                    "decimal_odds": decimal,
                    "sportsbook": bookmaker.get("name"),
                    "implied_probability": None if not decimal or decimal <= 1 else 1 / decimal,
                    "source": "api-football",
                })
    return rows

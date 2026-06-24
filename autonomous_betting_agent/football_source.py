"""Optional API-Football wrapper and normalizers.

All functions fail closed: missing keys, plan limits, or network errors return
empty data plus warnings instead of breaking local CSV mode.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any, Mapping

from .source_config import get_secret

BASE_URL = "https://v3.football.api-sports.io"


def _warning(message: str) -> tuple[list[dict[str, Any]], str]:
    return [], message


def _key() -> str:
    return get_secret("API_FOOTBALL_KEY")


@lru_cache(maxsize=128)
def _request(endpoint: str, query_items: tuple[tuple[str, str], ...]) -> tuple[dict[str, Any], str]:
    key = _key()
    if not key:
        return {}, "API-Football key missing; using local CSV mode."
    params = urllib.parse.urlencode(dict(query_items))
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += f"?{params}"
    request = urllib.request.Request(url, headers={"x-apisports-key": key})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:  # nosec - controlled endpoint
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {}, f"API-Football request failed: {exc}"
    errors = payload.get("errors")
    if errors:
        return payload, f"API-Football warning: {errors}"
    return payload, ""


def _items(endpoint: str, **params: Any) -> tuple[list[dict[str, Any]], str]:
    clean = tuple(sorted((key, str(value)) for key, value in params.items() if value not in (None, "")))
    payload, warning = _request(endpoint, clean)
    data = payload.get("response") if payload else []
    if not isinstance(data, list):
        data = []
    return data, warning


def fetch_api_football_fixtures(date: str | None = None, league: str | int | None = None, season: str | int | None = None) -> tuple[list[dict[str, Any]], str]:
    rows, warning = _items("fixtures", date=date, league=league, season=season)
    return [normalize_api_football_fixture(row) for row in rows], warning


def fetch_api_football_fixture_statistics(fixture_id: str | int) -> tuple[list[dict[str, Any]], str]:
    rows, warning = _items("fixtures/statistics", fixture=fixture_id)
    return [normalize_api_football_statistics(row) for row in rows], warning


def fetch_api_football_lineups(fixture_id: str | int) -> tuple[list[dict[str, Any]], str]:
    return _items("fixtures/lineups", fixture=fixture_id)


def fetch_api_football_injuries(fixture_id: str | int | None = None, team_id: str | int | None = None) -> tuple[list[dict[str, Any]], str]:
    return _items("injuries", fixture=fixture_id, team=team_id)


def fetch_api_football_standings(league: str | int, season: str | int) -> tuple[list[dict[str, Any]], str]:
    return _items("standings", league=league, season=season)


def fetch_api_football_odds(fixture_id: str | int | None = None, league: str | int | None = None, date: str | None = None) -> tuple[list[dict[str, Any]], str]:
    rows, warning = _items("odds", fixture=fixture_id, league=league, date=date)
    return [item for raw in rows for item in normalize_api_football_odds(raw)], warning


def normalize_api_football_fixture(raw: Mapping[str, Any]) -> dict[str, Any]:
    fixture = raw.get("fixture") or {}
    league = raw.get("league") or {}
    teams = raw.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    return {
        "game": f"{home.get('name', '')} vs {away.get('name', '')}".strip(" vs"),
        "sport": "Soccer",
        "league": league.get("name", ""),
        "start_time": fixture.get("date", ""),
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "fixture_id": fixture.get("id"),
        "source": "api-football",
    }


def normalize_api_football_statistics(raw: Mapping[str, Any]) -> dict[str, Any]:
    team = raw.get("team") or {}
    stats = raw.get("statistics") or []
    values: dict[str, Any] = {"team": team.get("name", ""), "source": "api-football"}
    for item in stats:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("type", "")).lower().replace(" ", "_")
        values[key] = item.get("value")
    return values


def _decimal(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 1 else None


def normalize_api_football_odds(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    fixture = raw.get("fixture") or {}
    league = raw.get("league") or {}
    bookmakers = raw.get("bookmakers") or []
    output: list[dict[str, Any]] = []
    for book in bookmakers:
        for bet in book.get("bets") or []:
            market = bet.get("name", "")
            for value in bet.get("values") or []:
                odds = _decimal(value.get("odd"))
                output.append({
                    "game": str(fixture.get("id", "")),
                    "sport": "Soccer",
                    "league": league.get("name", ""),
                    "fixture_id": fixture.get("id"),
                    "market": market,
                    "selection": value.get("value", ""),
                    "decimal_odds": odds,
                    "implied_probability": None if not odds else 1 / odds,
                    "sportsbook": book.get("name", ""),
                    "source": "api-football",
                })
    return output


def soccer_context_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source": "api-football",
        "soccer_stats_summary": "API-Football context available when fixture/statistics rows are provided or fetched.",
        "fixture_id": row.get("fixture_id"),
        "possession_edge": row.get("possession_edge"),
        "shots_edge": row.get("shots_edge"),
        "corner_edge": row.get("corner_edge"),
        "card_edge": row.get("card_edge"),
        "warnings": [],
        "timestamp": int(time.time()),
    }

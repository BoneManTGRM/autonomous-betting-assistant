from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping

GAME_KEYWORDS = {"gameid", "globalgameid", "hometeam", "awayteam", "homescore", "awayscore", "datetime", "status"}
PLAYER_KEYWORDS = {"playerid", "globalplayerid", "firstname", "lastname", "team", "position"}
TEAM_KEYWORDS = {"teamid", "globalteamid", "key", "city", "name", "conference", "division"}

GAME_OUTPUT_COLUMNS = [
    "sdio_dataset_type",
    "sdio_game_id",
    "sdio_global_game_id",
    "sport",
    "season",
    "week",
    "start_time",
    "status",
    "is_final",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "winner",
    "stadium_id",
    "source_quality_flags",
]

PLAYER_OUTPUT_COLUMNS = [
    "sdio_dataset_type",
    "sdio_player_id",
    "sdio_global_player_id",
    "sport",
    "first_name",
    "last_name",
    "display_name",
    "team",
    "position",
    "status",
    "injury_status",
    "source_quality_flags",
]

TEAM_OUTPUT_COLUMNS = [
    "sdio_dataset_type",
    "sdio_team_id",
    "sdio_global_team_id",
    "sport",
    "team_key",
    "city",
    "name",
    "full_name",
    "conference",
    "division",
    "source_quality_flags",
]


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(key): value for key, value in row.items()}


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lookup = _lookup(row)
    for name in names:
        value = lookup.get(_clean_key(name))
        if value not in (None, ""):
            return value
    return ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _number(value: Any) -> float | None:
    text = _text(value).replace(",", "")
    if not text or text.lower() in {"none", "null", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int_text(value: Any) -> str:
    number = _number(value)
    if number is None:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def _is_final(value: Any) -> bool:
    text = _text(value).lower()
    return text in {"final", "f", "closed", "completed", "complete", "final/ot", "final ot", "postponed", "canceled", "cancelled"}


def _winner(home_team: str, away_team: str, home_score: Any, away_score: Any, status: Any) -> str:
    if not _is_final(status):
        return ""
    home = _number(home_score)
    away = _number(away_score)
    if home is None or away is None:
        return ""
    if home > away:
        return home_team
    if away > home:
        return away_team
    return "push"


def infer_dataset_type(records: list[Mapping[str, Any]]) -> str:
    if not records:
        return "unknown"
    keys = {_clean_key(key) for record in records[:10] for key in record.keys()}
    if len(keys & GAME_KEYWORDS) >= 3:
        return "games"
    if len(keys & PLAYER_KEYWORDS) >= 3:
        return "players"
    if len(keys & TEAM_KEYWORDS) >= 3:
        return "teams"
    return "unknown"


def _quality_flags(required: Mapping[str, Any]) -> str:
    flags = [f"missing_{key}" for key, value in required.items() if value in (None, "")]
    return "; ".join(flags)


def normalize_game_record(row: Mapping[str, Any], *, sport: str = "") -> dict[str, Any]:
    home_team = _text(_first(row, ("HomeTeam", "HomeTeamKey", "Home", "HomeName")))
    away_team = _text(_first(row, ("AwayTeam", "AwayTeamKey", "Away", "AwayName")))
    home_score = _first(row, ("HomeScore", "Score_Home", "HomeTeamScore"))
    away_score = _first(row, ("AwayScore", "Score_Away", "AwayTeamScore"))
    status = _text(_first(row, ("Status", "GameStatus", "StatusDetail")))
    start_time = _text(_first(row, ("DateTime", "DateTimeUTC", "Day", "StartTime", "GameTime")))
    game_id = _int_text(_first(row, ("GameID", "GameId", "Id")))
    record = {
        "sdio_dataset_type": "games",
        "sdio_game_id": game_id,
        "sdio_global_game_id": _int_text(_first(row, ("GlobalGameID", "GlobalGameId"))),
        "sport": sport,
        "season": _int_text(_first(row, ("Season", "SeasonYear"))),
        "week": _int_text(_first(row, ("Week", "Round"))),
        "start_time": start_time,
        "status": status,
        "is_final": str(_is_final(status)).lower(),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": _int_text(home_score),
        "away_score": _int_text(away_score),
        "winner": _winner(home_team, away_team, home_score, away_score, status),
        "stadium_id": _int_text(_first(row, ("StadiumID", "StadiumId", "VenueID", "VenueId"))),
    }
    record["source_quality_flags"] = _quality_flags({"sdio_game_id": record["sdio_game_id"], "home_team": home_team, "away_team": away_team, "start_time": start_time})
    return record


def normalize_player_record(row: Mapping[str, Any], *, sport: str = "") -> dict[str, Any]:
    first = _text(_first(row, ("FirstName", "First", "GivenName")))
    last = _text(_first(row, ("LastName", "Last", "Surname")))
    display = _text(_first(row, ("Name", "FullName", "DisplayName"))) or " ".join(part for part in (first, last) if part)
    record = {
        "sdio_dataset_type": "players",
        "sdio_player_id": _int_text(_first(row, ("PlayerID", "PlayerId", "Id"))),
        "sdio_global_player_id": _int_text(_first(row, ("GlobalPlayerID", "GlobalPlayerId"))),
        "sport": sport,
        "first_name": first,
        "last_name": last,
        "display_name": display,
        "team": _text(_first(row, ("Team", "TeamKey", "CurrentTeam", "PlayerTeam"))),
        "position": _text(_first(row, ("Position", "FantasyPosition"))),
        "status": _text(_first(row, ("Status", "PlayerStatus", "Active"))),
        "injury_status": _text(_first(row, ("InjuryStatus", "InjuryNotes", "InjuryBodyPart"))),
    }
    record["source_quality_flags"] = _quality_flags({"sdio_player_id": record["sdio_player_id"], "display_name": display, "team": record["team"]})
    return record


def normalize_team_record(row: Mapping[str, Any], *, sport: str = "") -> dict[str, Any]:
    city = _text(_first(row, ("City", "Market")))
    name = _text(_first(row, ("Name", "TeamName", "Nickname")))
    full_name = _text(_first(row, ("FullName", "TeamFullName"))) or " ".join(part for part in (city, name) if part)
    record = {
        "sdio_dataset_type": "teams",
        "sdio_team_id": _int_text(_first(row, ("TeamID", "TeamId", "Id"))),
        "sdio_global_team_id": _int_text(_first(row, ("GlobalTeamID", "GlobalTeamId"))),
        "sport": sport,
        "team_key": _text(_first(row, ("Key", "Team", "TeamKey", "Abbreviation"))),
        "city": city,
        "name": name,
        "full_name": full_name,
        "conference": _text(_first(row, ("Conference", "League"))),
        "division": _text(_first(row, ("Division",))),
    }
    record["source_quality_flags"] = _quality_flags({"team_key": record["team_key"], "name": name})
    return record


def normalize_records(records: list[Mapping[str, Any]], *, dataset_type: str = "auto", sport: str = "") -> list[dict[str, Any]]:
    kind = infer_dataset_type(records) if dataset_type == "auto" else dataset_type.lower()
    if kind == "games":
        return [normalize_game_record(record, sport=sport) for record in records]
    if kind == "players":
        return [normalize_player_record(record, sport=sport) for record in records]
    if kind == "teams":
        return [normalize_team_record(record, sport=sport) for record in records]
    return [dict(record) for record in records]


def write_normalized_csv(records: list[Mapping[str, Any]], path: str | Path, *, dataset_type: str = "auto", sport: str = "") -> list[dict[str, Any]]:
    normalized = normalize_records(records, dataset_type=dataset_type, sport=sport)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _fieldnames_for(dataset_type if dataset_type != "auto" else infer_dataset_type(records), normalized)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in normalized:
            writer.writerow({key: record.get(key, "") for key in fieldnames})
    return normalized


def _fieldnames_for(dataset_type: str, records: list[Mapping[str, Any]]) -> list[str]:
    if dataset_type == "games":
        return GAME_OUTPUT_COLUMNS
    if dataset_type == "players":
        return PLAYER_OUTPUT_COLUMNS
    if dataset_type == "teams":
        return TEAM_OUTPUT_COLUMNS
    return sorted({key for record in records for key in record.keys()})
